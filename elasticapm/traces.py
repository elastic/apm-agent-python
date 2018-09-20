import datetime
import functools
import logging
import random
import re
import threading
import timeit
import uuid

from elasticapm.conf import constants
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.utils import compat, encoding, get_name_from_func

__all__ = ("capture_span", "tag", "set_transaction_name", "set_custom_context", "set_user_context")

error_logger = logging.getLogger("elasticapm.errors")

_time_func = timeit.default_timer


TAG_RE = re.compile('^[^.*"]+$')


try:
    from elasticapm.context.contextvars import get_transaction, set_transaction, get_span, set_span
except ImportError:
    from elasticapm.context.threadlocal import get_transaction, set_transaction, get_span, set_span


class Transaction(object):
    def __init__(self, store, transaction_type="custom", is_sampled=True):
        self.id = str(uuid.uuid4())
        self.trace_id = None  # for later use in distributed tracing
        self.timestamp = datetime.datetime.utcnow()
        self.start_time = _time_func()
        self.name = None
        self.duration = None
        self.result = None
        self.transaction_type = transaction_type
        self._store = store

        self.spans = []
        self.dropped_spans = 0
        self.context = {}
        self.tags = {}

        self.is_sampled = is_sampled
        self._span_counter = 0

    def end_transaction(self, skip_frames=8):
        self.duration = _time_func() - self.start_time

    def begin_span(self, name, span_type, context=None, leaf=False):
        parent_span = get_span()
        store = self._store
        if parent_span and parent_span.leaf:
            span = DroppedSpan(parent_span, leaf=True)
        elif store.max_spans and self._span_counter > store.max_spans - 1:
            self.dropped_spans += 1
            span = DroppedSpan(parent_span)
            self._span_counter += 1
        else:
            start = _time_func() - self.start_time
            span = Span(self._span_counter, self.id, self.trace_id, name, span_type, start, context, leaf)
            span.frames = store.frames_collector_func()
            span.parent = parent_span
            self._span_counter += 1
        set_span(span)
        return span

    def end_span(self, skip_frames):
        span = get_span()
        if span is None:
            raise LookupError()
        if isinstance(span, DroppedSpan):
            set_span(span.parent)
            return

        span.duration = _time_func() - span.start_time - self.start_time

        if not self._store.span_frames_min_duration or span.duration >= self._store.span_frames_min_duration:
            span.frames = self._store.frames_processing_func(span.frames)[skip_frames:]
        else:
            span.frames = None
        self.spans.append(span)
        set_span(span.parent)
        self._store.queue_func(SPAN, span.to_dict())
        return span

    def to_dict(self):
        self.context["tags"] = self.tags
        result = {
            "id": self.id,
            "trace_id": self.trace_id,
            "name": encoding.keyword_field(self.name or ""),
            "type": encoding.keyword_field(self.transaction_type),
            "duration": self.duration * 1000,  # milliseconds
            "result": encoding.keyword_field(str(self.result)),
            "timestamp": self.timestamp.strftime(constants.TIMESTAMP_FORMAT),
            "sampled": self.is_sampled,
            "span_count": {"started": self._span_counter - self.dropped_spans, "dropped": self.dropped_spans},
        }
        if self.is_sampled:
            result["context"] = self.context
        return result


class Span(object):
    __slots__ = (
        "idx",
        "transaction_id",
        "trace_id",
        "name",
        "type",
        "context",
        "leaf",
        "start_time",
        "duration",
        "parent",
        "frames",
    )

    def __init__(self, idx, transaction_id, trace_id, name, span_type, start_time, context=None, leaf=False):
        """
        Create a new Span

        :param idx: Index of this span
        :param name: Generic name of the span
        :param span_type: type of the span
        :param start_time: start time relative to the transaction
        :param context: context dictionary
        :param leaf: is this transaction a leaf transaction?
        """
        self.idx = idx
        self.transaction_id = transaction_id
        self.trace_id = trace_id
        self.name = name
        self.type = span_type
        self.context = context
        self.leaf = leaf
        self.start_time = start_time
        self.duration = None
        self.parent = None
        self.frames = None

    def to_dict(self):
        result = {
            "id": compat.text_type(self.idx),
            "transaction_id": self.transaction_id,
            "trace_id": self.trace_id,
            "name": encoding.keyword_field(self.name),
            "type": encoding.keyword_field(self.type),
            "start": self.start_time * 1000,  # milliseconds
            "duration": self.duration * 1000,  # milliseconds
            "parent": self.parent.idx if self.parent else None,
            "context": self.context,
        }
        if self.frames:
            result["stacktrace"] = self.frames
        return result


class DroppedSpan(object):
    __slots__ = ("leaf", "parent")

    def __init__(self, parent, leaf=False):
        self.parent = parent
        self.leaf = leaf


class TransactionsStore(object):
    def __init__(
        self,
        frames_collector_func,
        frames_processing_func,
        queue_func,
        sample_rate=1.0,
        max_spans=0,
        span_frames_min_duration=None,
        ignore_patterns=None,
    ):
        self.cond = threading.Condition()
        self.max_spans = max_spans
        self.queue_func = queue_func
        self.frames_processing_func = frames_processing_func
        self.frames_collector_func = frames_collector_func
        self._transactions = []
        self._last_collect = _time_func()
        self._ignore_patterns = [re.compile(p) for p in ignore_patterns or []]
        self._sample_rate = sample_rate
        if span_frames_min_duration in (-1, None):
            # both None and -1 mean "no minimum"
            self.span_frames_min_duration = None
        else:
            self.span_frames_min_duration = span_frames_min_duration / 1000.0

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

    def __len__(self):
        with self.cond:
            return len(self._transactions)

    def begin_transaction(self, transaction_type):
        """
        Start a new transactions and bind it in a thread-local variable

        :returns the Transaction object
        """
        is_sampled = self._sample_rate == 1.0 or self._sample_rate > random.random()
        transaction = Transaction(self, transaction_type, is_sampled=is_sampled)
        set_transaction(transaction)
        return transaction

    def _should_ignore(self, transaction_name):
        for pattern in self._ignore_patterns:
            if pattern.search(transaction_name):
                return True
        return False

    def end_transaction(self, result=None, transaction_name=None):
        transaction = get_transaction(clear=True)
        if transaction:
            transaction.end_transaction()
            if transaction.name is None:
                transaction.name = transaction_name if transaction_name is not None else ""
            if self._should_ignore(transaction.name):
                return
            if transaction.result is None:
                transaction.result = result
            self.queue_func(TRANSACTION, transaction.to_dict())
        return transaction


class capture_span(object):
    def __init__(self, name=None, span_type="code.custom", extra=None, skip_frames=0, leaf=False):
        self.name = name
        self.type = span_type
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
        if transaction and transaction.is_sampled:
            transaction.begin_span(self.name, self.type, context=self.extra, leaf=self.leaf)

    def __exit__(self, exc_type, exc_val, exc_tb):
        transaction = get_transaction()
        if transaction and transaction.is_sampled:
            try:
                transaction.end_span(self.skip_frames)
            except LookupError:
                error_logger.info("ended non-existing span %s of type %s", self.name, self.type)


def tag(**tags):
    """
    Tags current transaction. Both key and value of the tag should be strings.
    """
    transaction = get_transaction()
    for name, value in tags.items():
        if not transaction:
            error_logger.warning("Ignored tag %s. No transaction currently active.", name)
            return
        if TAG_RE.match(name):
            transaction.tags[compat.text_type(name)] = encoding.keyword_field(compat.text_type(value))
        else:
            error_logger.warning("Ignored tag %s. Tag names can't contain stars, dots or double quotes.", name)


def set_transaction_name(name, override=True):
    transaction = get_transaction()
    if not transaction:
        return
    if transaction.name is None or override:
        transaction.name = name


def set_transaction_result(result, override=True):
    transaction = get_transaction()
    if not transaction:
        return
    if transaction.result is None or override:
        transaction.result = result


def set_context(data, key="custom"):
    transaction = get_transaction()
    if not transaction:
        return
    if callable(data) and transaction.is_sampled:
        data = data()
    if key in transaction.context:
        transaction.context[key].update(data)
    else:
        transaction.context[key] = data


set_custom_context = functools.partial(set_context, key="custom")


def set_user_context(username=None, email=None, user_id=None):
    data = {}
    if username is not None:
        data["username"] = encoding.keyword_field(username)
    if email is not None:
        data["email"] = encoding.keyword_field(email)
    if user_id is not None:
        data["id"] = encoding.keyword_field(user_id)
    set_context(data, "user")
