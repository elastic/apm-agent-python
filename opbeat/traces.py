import functools
import logging
import threading
import time
from collections import defaultdict
from datetime import datetime

from opbeat.utils import get_name_from_func
from opbeat.utils.encoding import force_text
from opbeat.utils.lru import LRUCache

error_logger = logging.getLogger('opbeat.errors')

all = ('trace', )

thread_local = threading.local()
thread_local.transaction_traces = []
thread_local.transaction = None


def get_transaction():
    """
    Get the transaction registered for the current thread.

    :return:
    :rtype: Transaction
    """
    return getattr(thread_local, "transaction", None)


class Transaction(object):
    _lrucache = LRUCache(maxsize=5000)

    def __init__(self, start_time, get_frames, client,
                 kind="transaction.django"):
        self.start_time = start_time
        self.get_frames = get_frames
        self.client = client

        self.transaction_traces = []
        self.trace_stack = []
        self.ignore_subtree = False

        # The transaction is a trace as well
        self.begin_trace("transaction", "transaction")

    def end_transaction(self, skip_frames=8):
        # End the "transaction" trace started above
        return self.end_trace(skip_frames)

    def begin_trace(self, signature, kind, extra=None, leaf=False):
        # If we were already called with `leaf=True`, we'll just push
        # a placeholder on the stack.
        if self.ignore_subtree:
            self.trace_stack.append(None)
            return None

        if leaf:
            self.ignore_subtree = True

        abs_start = time.time()
        trace = Trace(signature, kind, abs_start, extra)
        self.trace_stack.append(trace)
        return trace

    def end_trace(self, skip_frames):
        trace = self.trace_stack.pop()
        if trace is None:
            return None

        self.ignore_subtree = False

        duration = (time.time() - trace.abs_start_time)*1000

        if self.trace_stack:
            parent_start_time = self.trace_stack[-1].abs_start_time
        else:
            parent_start_time = 0.0
        rel_start_time = (trace.abs_start_time - parent_start_time) * 1000

        parents = [s.signature for s in self.trace_stack]

        trace.parents = tuple(parents)
        trace.trace_duration = duration
        trace.rel_start_time = rel_start_time

        if not self._lrucache.has_key(trace.fingerprint):
            self._lrucache.set(trace.fingerprint)
            frames = self.get_frames()[skip_frames:]
            trace.frames = frames

        self.transaction_traces.append(trace)

        return trace


class AbstractTrace(object):
    def __init__(self, signature, kind, extra):
        self.signature = signature
        self.kind = kind
        self.extra = extra

        self.transaction = None
        self.transaction_duration = None
        self.parents = None
        self.frames = None


    @property
    def fingerprint(self):
        return self.transaction, self.parents, self.signature, self.kind


class Trace(AbstractTrace):
    def __init__(self, signature, kind, abs_start_time, extra=None, leaf=False):
        super(Trace, self).__init__(signature, kind, extra)

        self.leaf = leaf
        self.abs_start_time = abs_start_time
        self.trace_duration = None
        self.rel_start_time = None


class TraceGroup(AbstractTrace):
    def _decode(self, param):
        try:
            return force_text(param, strings_only=True)
        except UnicodeDecodeError:
            return '(encoded string)'

    def __init__(self, trace):
        super(TraceGroup, self).__init__(trace.signature, trace.kind, trace.extra)
        self.parents = trace.parents
        self.frames = trace.frames
        self.transaction = trace.transaction

        self.traces = []

    def add(self, trace):
        self.traces.append(trace)

    def as_dict(self):
        # Merge frames into extra
        extra = dict(self.extra or {})
        if self.frames:
            extra['_frames'] = self.frames

        return {
            "transaction": self.transaction,
            "durations": [(t.trace_duration, t.transaction_duration)
                          for t in self.traces],
            "signature": self.signature,
            "kind": self.kind,
            "parents": self.parents,
            "extra": extra,
            "start_time": min([t.rel_start_time for t in self.traces]),
        }


class _RequestGroup(object):
    def __init__(self, transaction, response_code, minute):
        self.transaction = transaction
        self.response_code = response_code
        self.minute = minute
        self.durations = []

    @property
    def fingerprint(self):
        return self.transaction, self.response_code, self.minute

    def add(self, elapsed):
        self.durations.append(elapsed)

    def as_dict(self):
        return {
            "transaction": self.transaction,
            "result": self.response_code,
            "timestamp": datetime.utcfromtimestamp(self.minute).isoformat() + "Z",
            "durations": self.durations
        }


class RequestsStore(object):
    def __init__(self, get_frames, collect_frequency):
        self.cond = threading.Condition()
        self._get_frames = get_frames
        self._transactions = {}
        self._traces = defaultdict(list)
        self.collect_frequency = collect_frequency
        self._last_collect = time.time()

    def _add_transaction(self, elapsed, transaction, response_code):
        with self.cond:
            requestgroup = _RequestGroup(transaction, response_code,
                                        int(time.time()/60)*60)

            if requestgroup.fingerprint not in self._transactions:
                self._transactions[requestgroup.fingerprint] = requestgroup

            self._transactions[requestgroup.fingerprint].add(elapsed)
            self.cond.notify()

    def get_all(self, blocking=False):
        with self.cond:
            # If blocking is true, always return at least 1 item
            while blocking and len(self._traces) == 0:
                self.cond.wait()
            transactions, self._transactions = self._transactions, {}
            traces, self._traces = self._traces, {}
        self._last_collect = time.time()
        return ([v.as_dict() for v in transactions.values()],
                [v.as_dict() for v in traces.values()],)

    def should_collect(self):
        return (time.time() - self._last_collect) >= self.collect_frequency

    def __len__(self):
        with self.cond:
            return sum([len(v.durations) for v in self._transactions.values()])

    def transaction_start(self, client, kind):
        """
        Start a new transactions and bind it in a thread-local variable

        """
        thread_local.transaction = Transaction(
            time.time(),
            self._get_frames,
            client,
            kind,
        )

    def _add_traces(self, traces):
        with self.cond:
            for trace in traces:
                if trace.fingerprint not in self._traces:
                    self._traces[trace.fingerprint] = TraceGroup(trace)
                self._traces[trace.fingerprint].add(trace)
            self.cond.notify()

    def transaction_end(self, response_code, transaction_name):
        transaction = get_transaction()
        if transaction:
            elapsed = (time.time() - transaction.start_time)*1000

            transaction.end_transaction()

            transaction_traces = transaction.transaction_traces

            # Take all the traces accumulated during the transaction,
            # set the transaction name on them and merge them into the dict
            for trace in transaction_traces:
                trace.transaction = transaction_name
                trace.transaction_duration = elapsed

            self._add_traces(transaction_traces)

            self._add_transaction(elapsed, transaction_name,
                                  response_code)

            # Reset thread local transaction to subsequent call to this method
            # behaves as expected.
            thread_local.transaction = None


class trace(object):
    def __init__(self, signature=None, kind='code.custom', extra=None,
                 skip_frames=0, leaf=False):
        self.signature = signature
        self.kind = kind
        self.extra = extra
        self.skip_frames = skip_frames
        self.leaf = leaf

        self.transaction = None

    def __call__(self, func):
        self.signature = self.signature or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            with self:
                return func(*args, **kwds)

        return decorated

    def __enter__(self):
        self.transaction = get_transaction()

        if self.transaction:
            self.transaction.begin_trace(self.signature, self.kind, self.extra,
                                         self.leaf)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            self.transaction.end_trace(self.skip_frames)
