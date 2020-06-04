#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import functools
import random
import re
import threading
import time
import timeit
import warnings
from collections import defaultdict

from elasticapm.conf import constants
from elasticapm.conf.constants import LABEL_RE, SPAN, TRANSACTION
from elasticapm.context import init_execution_context
from elasticapm.metrics.base_metrics import Timer
from elasticapm.utils import compat, encoding, get_name_from_func
from elasticapm.utils.deprecation import deprecated
from elasticapm.utils.disttracing import TraceParent, TracingOptions
from elasticapm.utils.logging import get_logger

__all__ = ("capture_span", "tag", "label", "set_transaction_name", "set_custom_context", "set_user_context")

error_logger = get_logger("elasticapm.errors")
logger = get_logger("elasticapm.traces")

_time_func = timeit.default_timer


execution_context = init_execution_context()


class ChildDuration(object):
    __slots__ = ("obj", "_nesting_level", "_start", "_duration", "_lock")

    def __init__(self, obj):
        self.obj = obj
        self._nesting_level = 0
        self._start = None
        self._duration = 0
        self._lock = threading.Lock()

    def start(self, timestamp):
        with self._lock:
            self._nesting_level += 1
            if self._nesting_level == 1:
                self._start = timestamp

    def stop(self, timestamp):
        with self._lock:
            self._nesting_level -= 1
            if self._nesting_level == 0:
                self._duration += timestamp - self._start

    @property
    def duration(self):
        return self._duration


class BaseSpan(object):
    def __init__(self, labels=None):
        self._child_durations = ChildDuration(self)
        self.labels = {}
        if labels:
            self.label(**labels)

    def child_started(self, timestamp):
        self._child_durations.start(timestamp)

    def child_ended(self, timestamp):
        self._child_durations.stop(timestamp)

    def end(self, skip_frames=0, duration=None):
        raise NotImplementedError()

    def label(self, **labels):
        """
        Label this span with one or multiple key/value labels. Keys should be strings, values can be strings, booleans,
        or numerical values (int, float, Decimal)

            span_obj.label(key1="value1", key2=True, key3=42)

        Note that keys will be dedotted, replacing dot (.), star (*) and double quote (") with an underscore (_)

        :param labels: key/value pairs of labels
        :return: None
        """
        labels = encoding.enforce_label_format(labels)
        self.labels.update(labels)

    @deprecated("transaction/span.label()")
    def tag(self, **tags):
        """
        This method is deprecated, please use "label()" instead.

        Tag this span with one or multiple key/value tags. Both the values should be strings

            span_obj.tag(key1="value1", key2="value2")

        Note that keys will be dedotted, replacing dot (.), star (*) and double quote (") with an underscore (_)

        :param tags: key/value pairs of tags
        :return: None
        """
        for key in tags.keys():
            self.labels[LABEL_RE.sub("_", compat.text_type(key))] = encoding.keyword_field(compat.text_type(tags[key]))


class Transaction(BaseSpan):
    def __init__(self, tracer, transaction_type="custom", trace_parent=None, is_sampled=True, start=None):
        self.id = "%016x" % random.getrandbits(64)
        self.trace_parent = trace_parent
        if start:
            self.timestamp = self.start_time = start
        else:
            self.timestamp, self.start_time = time.time(), _time_func()
        self.name = None
        self.duration = None
        self.result = None
        self.transaction_type = transaction_type
        self.tracer = tracer

        self.dropped_spans = 0
        self.context = {}

        self.is_sampled = is_sampled
        self._span_counter = 0
        self._span_timers = defaultdict(Timer)
        self._span_timers_lock = threading.Lock()
        try:
            self._breakdown = self.tracer._agent._metrics.get_metricset(
                "elasticapm.metrics.sets.breakdown.BreakdownMetricSet"
            )
        except (LookupError, AttributeError):
            self._breakdown = None
        try:
            self._transaction_metrics = self.tracer._agent._metrics.get_metricset(
                "elasticapm.metrics.sets.transactions.TransactionsMetricSet"
            )
        except (LookupError, AttributeError):
            self._transaction_metrics = None
        super(Transaction, self).__init__()

    def end(self, skip_frames=0, duration=None):
        self.duration = duration if duration is not None else (_time_func() - self.start_time)
        if self._transaction_metrics:
            self._transaction_metrics.timer(
                "transaction.duration",
                reset_on_collect=True,
                **{"transaction.name": self.name, "transaction.type": self.transaction_type}
            ).update(self.duration)
        if self._breakdown:
            for (span_type, span_subtype), timer in compat.iteritems(self._span_timers):
                labels = {
                    "span.type": span_type,
                    "transaction.name": self.name,
                    "transaction.type": self.transaction_type,
                }
                if span_subtype:
                    labels["span.subtype"] = span_subtype
                self._breakdown.timer("span.self_time", reset_on_collect=True, **labels).update(*timer.val)
            labels = {"transaction.name": self.name, "transaction.type": self.transaction_type}
            if self.is_sampled:
                self._breakdown.counter("transaction.breakdown.count", reset_on_collect=True, **labels).inc()
                self._breakdown.timer(
                    "span.self_time",
                    reset_on_collect=True,
                    **{"span.type": "app", "transaction.name": self.name, "transaction.type": self.transaction_type}
                ).update(self.duration - self._child_durations.duration)

    def _begin_span(
        self,
        name,
        span_type,
        context=None,
        leaf=False,
        labels=None,
        parent_span_id=None,
        span_subtype=None,
        span_action=None,
        sync=None,
        start=None,
    ):
        parent_span = execution_context.get_span()
        tracer = self.tracer
        if parent_span and parent_span.leaf:
            span = DroppedSpan(parent_span, leaf=True)
        elif tracer.config.transaction_max_spans and self._span_counter > tracer.config.transaction_max_spans - 1:
            self.dropped_spans += 1
            span = DroppedSpan(parent_span)
            self._span_counter += 1
        else:
            span = Span(
                transaction=self,
                name=name,
                span_type=span_type or "code.custom",
                context=context,
                leaf=leaf,
                labels=labels,
                parent=parent_span,
                parent_span_id=parent_span_id,
                span_subtype=span_subtype,
                span_action=span_action,
                sync=sync,
                start=start,
            )
            span.frames = tracer.frames_collector_func()
            self._span_counter += 1
        execution_context.set_span(span)
        return span

    def begin_span(
        self,
        name,
        span_type,
        context=None,
        leaf=False,
        labels=None,
        span_subtype=None,
        span_action=None,
        sync=None,
        start=None,
    ):
        """
        Begin a new span
        :param name: name of the span
        :param span_type: type of the span
        :param context: a context dict
        :param leaf: True if this is a leaf span
        :param labels: a flat string/string dict of labels
        :param span_subtype: sub type of the span, e.g. "postgresql"
        :param span_action: action of the span , e.g. "query"
        :param sync: indicate if the span is synchronous or not. In most cases, `None` should be used
        :param start: timestamp, mostly useful for testing
        :return: the Span object
        """
        return self._begin_span(
            name,
            span_type,
            context=context,
            leaf=leaf,
            labels=labels,
            parent_span_id=None,
            span_subtype=span_subtype,
            span_action=span_action,
            sync=sync,
            start=start,
        )

    def end_span(self, skip_frames=0, duration=None):
        """
        End the currently active span
        :param skip_frames: numbers of frames to skip in the stack trace
        :param duration: override duration, mostly useful for testing
        :return: the ended span
        """
        span = execution_context.get_span()
        if span is None:
            raise LookupError()

        span.end(skip_frames=skip_frames, duration=duration)
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
        self.context["tags"] = self.labels
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

    def track_span_duration(self, span_type, span_subtype, self_duration):
        # TODO: once asynchronous spans are supported, we should check if the transaction is already finished
        # TODO: and, if it has, exit without tracking.
        with self._span_timers_lock:
            self._span_timers[(span_type, span_subtype)].update(self_duration)


class Span(BaseSpan):
    __slots__ = (
        "id",
        "transaction",
        "name",
        "type",
        "subtype",
        "action",
        "context",
        "leaf",
        "timestamp",
        "start_time",
        "duration",
        "parent",
        "parent_span_id",
        "frames",
        "labels",
        "sync",
        "_child_durations",
    )

    def __init__(
        self,
        transaction,
        name,
        span_type,
        context=None,
        leaf=False,
        labels=None,
        parent=None,
        parent_span_id=None,
        span_subtype=None,
        span_action=None,
        sync=None,
        start=None,
    ):
        """
        Create a new Span

        :param transaction: transaction object that this span relates to
        :param name: Generic name of the span
        :param span_type: type of the span, e.g. db
        :param context: context dictionary
        :param leaf: is this span a leaf span?
        :param labels: a dict of labels
        :param parent_span_id: override of the span ID
        :param span_subtype: sub type of the span, e.g. mysql
        :param span_action: sub type of the span, e.g. query
        :param sync: indicate if the span was executed synchronously or asynchronously
        :param start: timestamp, mostly useful for testing
        """
        self.start_time = start or _time_func()
        self.id = "%016x" % random.getrandbits(64)
        self.transaction = transaction
        self.name = name
        self.context = context if context is not None else {}
        self.leaf = leaf
        # timestamp is bit of a mix of monotonic and non-monotonic time sources.
        # we take the (non-monotonic) transaction timestamp, and add the (monotonic) difference of span
        # start time and transaction start time. In this respect, the span timestamp is guaranteed to grow
        # monotonically with respect to the transaction timestamp
        self.timestamp = transaction.timestamp + (self.start_time - transaction.start_time)
        self.duration = None
        self.parent = parent
        self.parent_span_id = parent_span_id
        self.frames = None
        self.sync = sync
        if span_subtype is None and "." in span_type:
            # old style dottet type, let's split it up
            type_bits = span_type.split(".")
            if len(type_bits) == 2:
                span_type, span_subtype = type_bits[:2]
            else:
                span_type, span_subtype, span_action = type_bits[:3]
        self.type = span_type
        self.subtype = span_subtype
        self.action = span_action
        if self.transaction._breakdown:
            p = self.parent if self.parent else self.transaction
            p.child_started(self.start_time)
        super(Span, self).__init__(labels=labels)

    def to_dict(self):
        result = {
            "id": self.id,
            "transaction_id": self.transaction.id,
            "trace_id": self.transaction.trace_parent.trace_id,
            # use either the explicitly set parent_span_id, or the id of the parent, or finally the transaction id
            "parent_id": self.parent_span_id or (self.parent.id if self.parent else self.transaction.id),
            "name": encoding.keyword_field(self.name),
            "type": encoding.keyword_field(self.type),
            "subtype": encoding.keyword_field(self.subtype),
            "action": encoding.keyword_field(self.action),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "duration": self.duration * 1000,  # milliseconds
        }
        if self.sync is not None:
            result["sync"] = self.sync
        if self.labels:
            if self.context is None:
                self.context = {}
            self.context["tags"] = self.labels
        if self.context:
            result["context"] = self.context
        if self.frames:
            result["stacktrace"] = self.frames
        return result

    def end(self, skip_frames=0, duration=None):
        """
        End this span and queue it for sending.

        :param skip_frames: amount of frames to skip from the beginning of the stack trace
        :param duration: override duration, mostly useful for testing
        :return: None
        """
        tracer = self.transaction.tracer
        timestamp = _time_func()
        self.duration = duration if duration is not None else (timestamp - self.start_time)
        if not tracer.span_frames_min_duration or self.duration >= tracer.span_frames_min_duration:
            self.frames = tracer.frames_processing_func(self.frames)[skip_frames:]
        else:
            self.frames = None
        execution_context.set_span(self.parent)
        tracer.queue_func(SPAN, self.to_dict())
        if self.transaction._breakdown:
            p = self.parent if self.parent else self.transaction
            p.child_ended(self.start_time + self.duration)
            self.transaction.track_span_duration(
                self.type, self.subtype, self.duration - self._child_durations.duration
            )

    def update_context(self, key, data):
        """
        Update the context data for given key
        :param key: the key, e.g. "db"
        :param data: a dictionary
        :return: None
        """
        current = self.context.get(key, {})
        current.update(data)
        self.context[key] = current

    def __str__(self):
        return u"{}/{}/{}".format(self.name, self.type, self.subtype)


class DroppedSpan(BaseSpan):
    __slots__ = ("leaf", "parent", "id")

    def __init__(self, parent, leaf=False):
        self.parent = parent
        self.leaf = leaf
        self.id = None
        super(DroppedSpan, self).__init__()

    def end(self, skip_frames=0, duration=None):
        execution_context.set_span(self.parent)

    def child_started(self, timestamp):
        pass

    def child_ended(self, timestamp):
        pass

    def update_context(self, key, data):
        pass

    @property
    def type(self):
        return None

    @property
    def subtype(self):
        return None

    @property
    def action(self):
        return None

    @property
    def context(self):
        return None


class Tracer(object):
    def __init__(self, frames_collector_func, frames_processing_func, queue_func, config, agent):
        self.config = config
        self.queue_func = queue_func
        self.frames_processing_func = frames_processing_func
        self.frames_collector_func = frames_collector_func
        self._agent = agent
        self._ignore_patterns = [re.compile(p) for p in config.transactions_ignore_patterns or []]

    @property
    def span_frames_min_duration(self):
        if self.config.span_frames_min_duration in (-1, None):
            return None
        else:
            return self.config.span_frames_min_duration / 1000.0

    def begin_transaction(self, transaction_type, trace_parent=None, start=None):
        """
        Start a new transactions and bind it in a thread-local variable

        :param transaction_type: type of the transaction, e.g. "request"
        :param trace_parent: an optional TraceParent object
        :param start: override the start timestamp, mostly useful for testing

        :returns the Transaction object
        """
        if trace_parent:
            is_sampled = bool(trace_parent.trace_options.recorded)
        else:
            is_sampled = (
                self.config.transaction_sample_rate == 1.0 or self.config.transaction_sample_rate > random.random()
            )
        transaction = Transaction(self, transaction_type, trace_parent=trace_parent, is_sampled=is_sampled, start=start)
        if trace_parent is None:
            transaction.trace_parent = TraceParent(
                constants.TRACE_CONTEXT_VERSION,
                "%032x" % random.getrandbits(128),
                transaction.id,
                TracingOptions(recorded=is_sampled),
            )
        execution_context.set_transaction(transaction)
        return transaction

    def _should_ignore(self, transaction_name):
        for pattern in self._ignore_patterns:
            if pattern.search(transaction_name):
                return True
        return False

    def end_transaction(self, result=None, transaction_name=None, duration=None):
        """
        End the current transaction and queue it for sending
        :param result: result of the transaction, e.g. "OK" or 200
        :param transaction_name: name of the transaction
        :param duration: override duration, mostly useful for testing
        :return:
        """
        transaction = execution_context.get_transaction(clear=True)
        if transaction:
            if transaction.name is None:
                transaction.name = transaction_name if transaction_name is not None else ""
            transaction.end(duration=duration)
            if self._should_ignore(transaction.name):
                return
            if transaction.result is None:
                transaction.result = result
            self.queue_func(TRANSACTION, transaction.to_dict())
        return transaction


class capture_span(object):
    __slots__ = (
        "name",
        "type",
        "subtype",
        "action",
        "extra",
        "skip_frames",
        "leaf",
        "labels",
        "duration",
        "start",
        "sync",
    )

    def __init__(
        self,
        name=None,
        span_type="code.custom",
        extra=None,
        skip_frames=0,
        leaf=False,
        tags=None,
        labels=None,
        span_subtype=None,
        span_action=None,
        start=None,
        duration=None,
        sync=None,
    ):
        self.name = name
        self.type = span_type
        self.subtype = span_subtype
        self.action = span_action
        self.extra = extra
        self.skip_frames = skip_frames
        self.leaf = leaf
        if tags and not labels:
            warnings.warn(
                'The tags argument to capture_span is deprecated, use "labels" instead',
                category=DeprecationWarning,
                stacklevel=2,
            )
            labels = tags

        self.labels = labels
        self.start = start
        self.duration = duration
        self.sync = sync

    def __call__(self, func):
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            with self:
                return func(*args, **kwds)

        return decorated

    def __enter__(self):
        transaction = execution_context.get_transaction()
        if transaction and transaction.is_sampled:
            return transaction.begin_span(
                self.name,
                self.type,
                context=self.extra,
                leaf=self.leaf,
                labels=self.labels,
                span_subtype=self.subtype,
                span_action=self.action,
                start=self.start,
                sync=self.sync,
            )

    def __exit__(self, exc_type, exc_val, exc_tb):
        transaction = execution_context.get_transaction()

        if transaction and transaction.is_sampled:
            try:
                span = transaction.end_span(self.skip_frames, duration=self.duration)
                if exc_val and not isinstance(span, DroppedSpan):
                    try:
                        exc_val._elastic_apm_span_id = span.id
                    except AttributeError:
                        # could happen if the exception has __slots__
                        pass
            except LookupError:
                logger.info("ended non-existing span %s of type %s", self.name, self.type)


def label(**labels):
    """
    Labels current transaction. Keys should be strings, values can be strings, booleans,
    or numerical values (int, float, Decimal)

    :param labels: key/value map of labels
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        error_logger.warning("Ignored labels %s. No transaction currently active.", ", ".join(labels.keys()))
    else:
        transaction.label(**labels)


@deprecated("elasticapm.label")
def tag(**tags):
    """
    Tags current transaction. Both key and value of the label should be strings.
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        error_logger.warning("Ignored tags %s. No transaction currently active.", ", ".join(tags.keys()))
    else:
        transaction.tag(**tags)


def set_transaction_name(name, override=True):
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.name is None or override:
        transaction.name = name


def set_transaction_result(result, override=True):
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.result is None or override:
        transaction.result = result


def get_transaction_id():
    """
    Returns the current transaction ID
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    return transaction.id


def get_trace_id():
    """
    Returns the current trace ID
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    return transaction.trace_parent.trace_id if transaction.trace_parent else None


def get_span_id():
    """
    Returns the current span ID
    """
    span = execution_context.get_span()
    if not span:
        return
    return span.id


def set_context(data, key="custom"):
    """
    Attach contextual data to the current transaction and errors that happen during the current transaction.

    If the transaction is not sampled, this function becomes a no-op.

    :param data: a dictionary, or a callable that returns a dictionary
    :param key: the namespace for this data
    """
    transaction = execution_context.get_transaction()
    if not (transaction and transaction.is_sampled):
        return
    if callable(data):
        data = data()

    # remove invalid characters from key names
    for k in list(data.keys()):
        if LABEL_RE.search(k):
            data[LABEL_RE.sub("_", k)] = data.pop(k)

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
