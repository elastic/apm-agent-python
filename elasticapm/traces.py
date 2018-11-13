import functools
import logging
import random
import re
import time
import timeit

from elasticapm.conf import constants
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.utils import compat, encoding, get_name_from_func
from elasticapm.utils.disttracing import TraceParent, TracingOptions

__all__ = ("capture_span", "tag", "set_transaction_name", "set_custom_context", "set_user_context")

error_logger = logging.getLogger("elasticapm.errors")
logger = logging.getLogger("elasticapm.traces")

_time_func = timeit.default_timer


TAG_RE = re.compile('^[^.*"]+$')


try:
    from elasticapm.context.contextvars import get_transaction, set_transaction, get_span, set_span
except ImportError:
    from elasticapm.context.threadlocal import get_transaction, set_transaction, get_span, set_span


class Transaction(object):
    def __init__(self, tracer, transaction_type="custom", trace_parent=None, is_sampled=True):
        self.id = "%016x" % random.getrandbits(64)
        self.trace_parent = trace_parent
        self.timestamp, self.start_time = time.time(), _time_func()
        self.name = None
        self.duration = None
        self.result = None
        self.transaction_type = transaction_type
        self._tracer = tracer

        self.spans = []
        self.dropped_spans = 0
        self.context = {}
        self.tags = {}

        self.is_sampled = is_sampled
        self._span_counter = 0

    def end_transaction(self):
        self.duration = _time_func() - self.start_time

    def begin_span(self, name, span_type, context=None, leaf=False):
        parent_span = get_span()
        tracer = self._tracer
        if parent_span and parent_span.leaf:
            span = DroppedSpan(parent_span, leaf=True)
        elif tracer.max_spans and self._span_counter > tracer.max_spans - 1:
            self.dropped_spans += 1
            span = DroppedSpan(parent_span)
            self._span_counter += 1
        else:
            span = Span(transaction=self, name=name, span_type=span_type, context=context, leaf=leaf)
            span.frames = tracer.frames_collector_func()
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

        span.duration = _time_func() - span.start_time

        if not self._tracer.span_frames_min_duration or span.duration >= self._tracer.span_frames_min_duration:
            span.frames = self._tracer.frames_processing_func(span.frames)[skip_frames:]
        else:
            span.frames = None
        self.spans.append(span)
        set_span(span.parent)
        self._tracer.queue_func(SPAN, span.to_dict())
        return span

    def ensure_parent_id(self):
        """If current trace_parent has no span_id, generate one, then return it

        This is used to generate a span ID which the RUM agent will use to correlate
        the RUM transaction with the backend transaction.
        """
        if self.trace_parent.span_id == self.id:
            self.trace_parent.span_id = "%016x" % random.getrandbits(64)
            logger.debug("Set parent id to generated %s", self.trace_parent.span_id)
        return self.trace_parent.span_id

    def to_dict(self):
        self.context["tags"] = self.tags
        result = {
            "id": self.id,
            "trace_id": self.trace_parent.trace_id,
            "name": encoding.keyword_field(self.name or ""),
            "type": encoding.keyword_field(self.transaction_type),
            "duration": self.duration * 1000,  # milliseconds
            "result": encoding.keyword_field(str(self.result)),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "sampled": self.is_sampled,
            "span_count": {"started": self._span_counter - self.dropped_spans, "dropped": self.dropped_spans},
        }
        if self.trace_parent:
            result["trace_id"] = self.trace_parent.trace_id
            # only set parent_id if this transaction isn't the root
            if self.trace_parent.span_id and self.trace_parent.span_id != self.id:
                result["parent_id"] = self.trace_parent.span_id
        if self.is_sampled:
            result["context"] = self.context
        return result


class Span(object):
    __slots__ = (
        "id",
        "transaction",
        "name",
        "type",
        "context",
        "leaf",
        "timestamp",
        "start_time",
        "duration",
        "parent",
        "frames",
    )

    def __init__(self, transaction, name, span_type, context=None, leaf=False):
        """
        Create a new Span

        :param transaction: transaction object that this span relates to
        :param name: Generic name of the span
        :param span_type: type of the span
        :param context: context dictionary
        :param leaf: is this span a leaf span?
        """
        self.start_time = _time_func()
        self.id = "%016x" % random.getrandbits(64)
        self.transaction = transaction
        self.name = name
        self.type = span_type
        self.context = context
        self.leaf = leaf
        # timestamp is bit of a mix of monotonic and non-monotonic time sources.
        # we take the (non-monotonic) transaction timestamp, and add the (monotonic) difference of span
        # start time and transaction start time. In this respect, the span timestamp is guaranteed to grow
        # monotonically with respect to the transaction timestamp
        self.timestamp = transaction.timestamp + (self.start_time - transaction.start_time)
        self.duration = None
        self.parent = None
        self.frames = None

    def to_dict(self):
        result = {
            "id": self.id,
            "transaction_id": self.transaction.id,
            "trace_id": self.transaction.trace_parent.trace_id,
            "parent_id": self.parent.id if self.parent else self.transaction.id,
            "name": encoding.keyword_field(self.name),
            "type": encoding.keyword_field(self.type),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "duration": self.duration * 1000,  # milliseconds
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


class Tracer(object):
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
        self.max_spans = max_spans
        self.queue_func = queue_func
        self.frames_processing_func = frames_processing_func
        self.frames_collector_func = frames_collector_func
        self._ignore_patterns = [re.compile(p) for p in ignore_patterns or []]
        self._sample_rate = sample_rate
        if span_frames_min_duration in (-1, None):
            # both None and -1 mean "no minimum"
            self.span_frames_min_duration = None
        else:
            self.span_frames_min_duration = span_frames_min_duration / 1000.0

    def begin_transaction(self, transaction_type, trace_parent=None):
        """
        Start a new transactions and bind it in a thread-local variable

        :returns the Transaction object
        """
        if trace_parent:
            is_sampled = bool(trace_parent.trace_options.recorded)
        else:
            is_sampled = self._sample_rate == 1.0 or self._sample_rate > random.random()
        transaction = Transaction(self, transaction_type, trace_parent=trace_parent, is_sampled=is_sampled)
        if trace_parent is None:
            transaction.trace_parent = TraceParent(
                constants.TRACE_CONTEXT_VERSION,
                "%032x" % random.getrandbits(128),
                transaction.id,
                TracingOptions(recorded=is_sampled),
            )
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
            return transaction.begin_span(self.name, self.type, context=self.extra, leaf=self.leaf)

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
