import datetime
import functools
import logging
import re
import threading
import time
import uuid

from elasticapm.conf import defaults
from elasticapm.utils import compat, get_name_from_func
from elasticapm.utils.lru import LRUCache

__all__ = ('trace', 'tag')

error_logger = logging.getLogger('elasticapm.errors')

thread_local = threading.local()
thread_local.transaction = None


_time_func = time.time

TAG_RE = re.compile('^[^.*\"]+$')


def get_transaction(clear=False):
    """
    Get the transaction registered for the current thread.

    :return:
    :rtype: Transaction
    """
    transaction = getattr(thread_local, "transaction", None)
    if clear:
        thread_local.transaction = None
    return transaction


class Transaction(object):
    _lrucache = LRUCache(maxsize=5000)

    def __init__(self, get_frames, kind="custom"):
        self.id = uuid.uuid4()
        self.timestamp = datetime.datetime.utcnow()
        self.start_time = _time_func()
        self.name = None
        self.duration = None
        self.result = None
        self.kind = kind
        self.get_frames = get_frames

        self.traces = []
        self.trace_stack = []
        self.ignore_subtree = False
        self._context = {}
        self._tags = {}

        self._trace_counter = 0

    def end_transaction(self, skip_frames=8):
        self.duration = _time_func() - self.start_time

    def begin_trace(self, name, trace_type, context=None, leaf=False):
        # If we were already called with `leaf=True`, we'll just push
        # a placeholder on the stack.
        if self.ignore_subtree:
            self.trace_stack.append(None)
            return None

        if leaf:
            self.ignore_subtree = True

        start = _time_func() - self.start_time
        trace = Trace(self._trace_counter, name, trace_type, start, context)
        self._trace_counter += 1
        self.trace_stack.append(trace)
        return trace

    def end_trace(self, skip_frames):
        trace = self.trace_stack.pop()
        if trace is None:
            return None

        self.ignore_subtree = False

        trace.duration = _time_func() - trace.start_time - self.start_time

        if self.trace_stack:
            trace.parent = self.trace_stack[-1].idx

        trace.frames = self.get_frames()[skip_frames:]
        self.traces.append(trace)

        return trace

    def to_dict(self):
        self._context['tags'] = self._tags
        return {
            'id': str(self.id),
            'name': self.name,
            'type': self.kind,
            'duration': self.duration * 1000,  # milliseconds
            'result': str(self.result),
            'timestamp': self.timestamp.strftime(defaults.TIMESTAMP_FORMAT),
            'context': self._context,
            'traces': [
                trace_obj.to_dict() for trace_obj in self.traces
            ]
        }


class Trace(object):
    def __init__(self, idx, name, trace_type, start_time, context=None,
                 leaf=False):
        """
        Create a new trace

        :param idx: Index of this trace
        :param name: Generic name of the trace
        :param trace_type: type of the trace
        :param start_time: start time relative to the transaction
        :param context: context dictionary
        :param leaf: is this transaction a leaf transaction?
        """
        self.idx = idx
        self.name = name
        self.type = trace_type
        self.context = context
        self.leaf = leaf
        self.start_time = start_time
        self.duration = None
        self.transaction = None
        self.parent = None
        self.frames = None

    @property
    def fingerprint(self):
        return self.transaction, self.parent, self.name, self.type

    def to_dict(self):
        return {
            'id': self.idx,
            'name': self.name,
            'type': self.type,
            'start': self.start_time * 1000,  # milliseconds
            'duration': self.duration * 1000,  # milliseconds
            'parent': self.parent,
            'stacktrace': self.frames,
            'context': self.context
        }


class TransactionsStore(object):
    def __init__(self, get_frames, collect_frequency, ignore_patterns=None):
        self.cond = threading.Condition()
        self.collect_frequency = collect_frequency
        self._get_frames = get_frames
        self._transactions = []
        self._last_collect = _time_func()
        self._ignore_patterns = [re.compile(p) for p in ignore_patterns or []]

    def add_transaction(self, transaction):
        with self.cond:
            self._transactions.append(transaction)
            self.cond.notify()

    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self._transactions) == 0:
                self.cond.wait()
            transactions, self._transactions = self._transactions, []
        self._last_collect = _time_func()
        return transactions

    def should_collect(self):
        return (_time_func() - self._last_collect) >= self.collect_frequency

    def __len__(self):
        with self.cond:
            return len(self._transactions)

    def begin_transaction(self, transaction_type):
        """
        Start a new transactions and bind it in a thread-local variable

        :returns the Transaction object
        """
        transaction = Transaction(self._get_frames, transaction_type)
        thread_local.transaction = transaction
        return transaction

    def _should_ignore(self, transaction_name):
        for pattern in self._ignore_patterns:
            if pattern.search(transaction_name):
                return True
        return False

    def end_transaction(self, response_code, transaction_name):
        transaction = get_transaction(clear=True)
        if transaction:
            transaction.end_transaction()
            if self._should_ignore(transaction_name):
                return
            transaction.name = transaction_name
            transaction.result = response_code
            self.add_transaction(transaction.to_dict())
        return transaction


class trace(object):
    def __init__(self, name=None, trace_type='code.custom', extra=None,
                 skip_frames=0, leaf=False):
        self.name = name
        self.type = trace_type
        self.extra = extra
        self.skip_frames = skip_frames
        self.leaf = leaf

    def __call__(self, func):
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            with self:
                return func(*args, **kwds)

        return decorated

    def __enter__(self):
        transaction = get_transaction()

        if transaction:
            transaction.begin_trace(self.name, self.type, self.extra,
                                    self.leaf)

    def __exit__(self, exc_type, exc_val, exc_tb):
        transaction = get_transaction()

        if transaction:
            transaction.end_trace(self.skip_frames)


def tag(**tags):
    """
    Tags current transaction. Both key and value of the tag should be strings.

        import opbeat
        opbeat.tag(foo=bar)

    """
    transaction = get_transaction()
    for name, value in tags.items():
        if not transaction:
            error_logger.warning("Ignored tag %s. No transaction currently active.", name)
            return
        if TAG_RE.match(name):
            transaction._tags[compat.text_type(name)] = compat.text_type(value)
        else:
            error_logger.warning("Ignored tag %s. Tag names can't contain stars, dots or double quotes.", name)
