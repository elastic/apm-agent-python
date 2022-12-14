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
import urllib.parse
import warnings
from collections import defaultdict
from datetime import timedelta
from types import TracebackType
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type, TypeVar, Union

import elasticapm
from elasticapm.conf import constants
from elasticapm.conf.constants import LABEL_RE, SPAN, TRANSACTION
from elasticapm.context import init_execution_context
from elasticapm.metrics.base_metrics import Timer
from elasticapm.utils import encoding, get_name_from_func, nested_key, url_to_destination_resource
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger
from elasticapm.utils.time import time_to_perf_counter

__all__ = ("capture_span", "label", "set_transaction_name", "set_custom_context", "set_user_context")

error_logger = get_logger("elasticapm.errors")
logger = get_logger("elasticapm.traces")

_time_func = timeit.default_timer


execution_context = init_execution_context()

SpanType = Union["Span", "DroppedSpan"]
_AnnotatedFunctionT = TypeVar("_AnnotatedFunctionT")


class ChildDuration(object):
    __slots__ = ("obj", "_nesting_level", "_start", "_duration", "_lock")

    def __init__(self, obj: "BaseSpan"):
        self.obj = obj
        self._nesting_level: int = 0
        self._start: float = 0
        self._duration: timedelta = timedelta(seconds=0)
        self._lock = threading.Lock()

    def start(self, timestamp: float):
        with self._lock:
            self._nesting_level += 1
            if self._nesting_level == 1:
                self._start = timestamp

    def stop(self, timestamp: float):
        with self._lock:
            self._nesting_level -= 1
            if self._nesting_level == 0:
                self._duration += timedelta(seconds=timestamp - self._start)

    @property
    def duration(self) -> timedelta:
        return self._duration


class BaseSpan(object):
    def __init__(self, labels=None, start=None, links: Optional[Sequence[TraceParent]] = None):
        self._child_durations = ChildDuration(self)
        self.labels = {}
        self.outcome: Optional[str] = None
        self.compression_buffer: Optional[Union[Span, DroppedSpan]] = None
        self.compression_buffer_lock = threading.Lock()
        self.start_time: float = time_to_perf_counter(start) if start is not None else _time_func()
        self.ended_time: Optional[float] = None
        self.duration: Optional[timedelta] = None
        self.links: Optional[List[Dict[str, str]]] = None
        if links:
            for trace_parent in links:
                self.add_link(trace_parent)
        if labels:
            self.label(**labels)

    def child_started(self, timestamp):
        self._child_durations.start(timestamp)

    def child_ended(self, child: SpanType):
        with self.compression_buffer_lock:
            if not child.is_compression_eligible():
                if self.compression_buffer:
                    self.compression_buffer.report()
                    self.compression_buffer = None
                child.report()
            elif self.compression_buffer is None:
                self.compression_buffer = child
            elif not self.compression_buffer.try_to_compress(child):
                self.compression_buffer.report()
                self.compression_buffer = child

    def end(self, skip_frames: int = 0, duration: Optional[timedelta] = None):
        self.ended_time = _time_func()
        self.duration = duration if duration is not None else timedelta(seconds=self.ended_time - self.start_time)
        if self.compression_buffer:
            self.compression_buffer.report()
            self.compression_buffer = None

    def to_dict(self) -> dict:
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

    def add_link(self, trace_parent: TraceParent) -> None:
        """
        Causally link this span/transaction to another span/transaction
        """
        if self.links is None:
            self.links = []
        self.links.append({"trace_id": trace_parent.trace_id, "span_id": trace_parent.span_id})

    def set_success(self):
        self.outcome = constants.OUTCOME.SUCCESS

    def set_failure(self):
        self.outcome = constants.OUTCOME.FAILURE

    @staticmethod
    def get_dist_tracing_id() -> str:
        return "%016x" % random.getrandbits(64)

    @property
    def tracer(self) -> "Tracer":
        raise NotImplementedError()


class Transaction(BaseSpan):
    def __init__(
        self,
        tracer: "Tracer",
        transaction_type: str = "custom",
        trace_parent: Optional[TraceParent] = None,
        is_sampled: bool = True,
        start: Optional[float] = None,
        sample_rate: Optional[float] = None,
        links: Optional[Sequence[TraceParent]] = None,
    ):
        """
        tracer
            Tracer object
        transaction_type
            Transaction type
        trace_parent
            TraceParent object representing the parent trace and trace state
        is_sampled
            Whether or not this transaction is sampled
        start
            Optional start timestamp. This is expected to be an epoch timestamp
            in seconds (such as from `time.time()`). If it is not, it's recommended
            that a `duration` is passed into the `end()` method.
        sample_rate
            Sample rate which was used to decide whether to sample this transaction.
            This is reported to the APM server so that unsampled transactions can
            be extrapolated.
        links:
            A list of traceparents to link this transaction causally
        """
        self.id = self.get_dist_tracing_id()
        if not trace_parent:
            trace_parent = TraceParent.new(self.id, is_sampled)

        self.trace_parent: TraceParent = trace_parent
        self.timestamp = start if start is not None else time.time()
        self.name: Optional[str] = None
        self.result: Optional[str] = None
        self.transaction_type = transaction_type
        self._tracer = tracer
        # The otel bridge uses Transactions/Spans interchangeably -- storing
        # a reference to the Transaction in the Transaction simplifies things.
        self.transaction = self
        self.config_span_compression_enabled = tracer.config.span_compression_enabled
        self.config_span_compression_exact_match_max_duration = tracer.config.span_compression_exact_match_max_duration
        self.config_span_compression_same_kind_max_duration = tracer.config.span_compression_same_kind_max_duration
        self.config_exit_span_min_duration = tracer.config.exit_span_min_duration
        self.config_transaction_max_spans = tracer.config.transaction_max_spans

        self.dropped_spans: int = 0
        self.context: Dict[str, Any] = {}

        self._is_sampled = is_sampled
        self.sample_rate = sample_rate
        self._span_counter: int = 0
        self._span_timers: Dict[Tuple[str, str], Timer] = defaultdict(Timer)
        self._span_timers_lock = threading.Lock()
        self._dropped_span_statistics = defaultdict(lambda: {"count": 0, "duration.sum.us": 0})
        try:
            self._breakdown = self.tracer._agent.metrics.get_metricset(
                "elasticapm.metrics.sets.breakdown.BreakdownMetricSet"
            )
        except (LookupError, AttributeError):
            self._breakdown = None
        super().__init__(start=start)
        if links:
            for trace_parent in links:
                self.add_link(trace_parent)

    def end(self, skip_frames: int = 0, duration: Optional[timedelta] = None):
        super().end(skip_frames, duration)
        if self._breakdown:
            for (span_type, span_subtype), timer in self._span_timers.items():
                labels = {
                    "span.type": span_type,
                    "transaction.name": self.name,
                    "transaction.type": self.transaction_type,
                }
                if span_subtype:
                    labels["span.subtype"] = span_subtype
                val = timer.val
                self._breakdown.timer("span.self_time", reset_on_collect=True, unit="us", **labels).update(
                    val[0], val[1]
                )
            if self.is_sampled:
                self._breakdown.timer(
                    "span.self_time",
                    reset_on_collect=True,
                    unit="us",
                    **{"span.type": "app", "transaction.name": self.name, "transaction.type": self.transaction_type},
                ).update((self.duration - self._child_durations.duration).total_seconds() * 1_000_000)

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
        auto_activate=True,
        links: Optional[Sequence[TraceParent]] = None,
    ):
        parent_span = execution_context.get_span()
        tracer = self.tracer
        if parent_span and parent_span.leaf:
            span = DroppedSpan(parent_span, leaf=True)
        elif self.config_transaction_max_spans and self._span_counter > self.config_transaction_max_spans - 1:
            self.dropped_spans += 1
            span = DroppedSpan(parent_span, context=context)
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
                links=links,
            )
            span.frames = tracer.frames_collector_func()
            self._span_counter += 1
        if auto_activate:
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
        auto_activate=True,
        links: Optional[Sequence[TraceParent]] = None,
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
        :param auto_activate: whether to set this span in execution_context
        :param links: an optional list of traceparents to link this span with
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
            auto_activate=auto_activate,
            links=links,
        )

    def end_span(self, skip_frames: int = 0, duration: Optional[float] = None, outcome: str = "unknown"):
        """
        End the currently active span
        :param skip_frames: numbers of frames to skip in the stack trace
        :param duration: override duration, mostly useful for testing
        :param outcome: outcome of the span, either success, failure or unknown
        :return: the ended span
        """
        span = execution_context.get_span()
        if span is None:
            raise LookupError()

        # only overwrite span outcome if it is still unknown
        if not span.outcome or span.outcome == "unknown":
            span.outcome = outcome

        span.end(skip_frames=skip_frames, duration=duration)
        return span

    def ensure_parent_id(self) -> str:
        """If current trace_parent has no span_id, generate one, then return it

        This is used to generate a span ID which the RUM agent will use to correlate
        the RUM transaction with the backend transaction.
        """
        if self.trace_parent.span_id == self.id:
            self.trace_parent.span_id = "%016x" % random.getrandbits(64)
            logger.debug("Set parent id to generated %s", self.trace_parent.span_id)
        return self.trace_parent.span_id

    def to_dict(self) -> dict:
        self.context["tags"] = self.labels
        result = {
            "id": self.id,
            "trace_id": self.trace_parent.trace_id,
            "name": encoding.keyword_field(self.name or ""),
            "type": encoding.keyword_field(self.transaction_type),
            "duration": self.duration.total_seconds() * 1000,
            "result": encoding.keyword_field(str(self.result)),
            "timestamp": int(self.timestamp * 1_000_000),  # microseconds
            "outcome": self.outcome,
            "sampled": self.is_sampled,
            "span_count": {"started": self._span_counter, "dropped": self.dropped_spans},
        }
        if self._dropped_span_statistics:
            result["dropped_spans_stats"] = [
                {
                    "destination_service_resource": resource,
                    "service_target_type": target_type,
                    "service_target_name": target_name,
                    "outcome": outcome,
                    "duration": {"count": v["count"], "sum": {"us": int(v["duration.sum.us"])}},
                }
                for (resource, outcome, target_type, target_name), v in self._dropped_span_statistics.items()
            ]
        if self.sample_rate is not None:
            result["sample_rate"] = float(self.sample_rate)
        if self.trace_parent:
            result["trace_id"] = self.trace_parent.trace_id
            # only set parent_id if this transaction isn't the root
            if self.trace_parent.span_id and self.trace_parent.span_id != self.id:
                result["parent_id"] = self.trace_parent.span_id
        if self.links:
            result["links"] = self.links
        # faas context belongs top-level on the transaction
        if "faas" in self.context:
            result["faas"] = self.context.pop("faas")
        # otel attributes and spankind need to be top-level
        if "otel_spankind" in self.context:
            result["otel"] = {"span_kind": self.context.pop("otel_spankind")}
        # Some transaction_store_tests use the Tracer without a Client -- the
        # extra check against `get_client()` is here to make those tests pass
        if elasticapm.get_client() and elasticapm.get_client().check_server_version(gte=(7, 16)):
            if "otel_attributes" in self.context:
                if "otel" not in result:
                    result["otel"] = {"attributes": self.context.pop("otel_attributes")}
                else:
                    result["otel"]["attributes"] = self.context.pop("otel_attributes")
        else:
            # Attributes map to labels for older versions
            attributes = self.context.pop("otel_attributes", {})
            for key, value in attributes.items():
                result["context"]["tags"][key] = value
        if self.is_sampled:
            result["context"] = self.context
        return result

    def track_span_duration(self, span_type, span_subtype, self_duration):
        # TODO: once asynchronous spans are supported, we should check if the transaction is already finished
        # TODO: and, if it has, exit without tracking.
        with self._span_timers_lock:
            self._span_timers[(span_type, span_subtype)].update(self_duration.total_seconds() * 1_000_000)

    @property
    def is_sampled(self) -> bool:
        return self._is_sampled

    @is_sampled.setter
    def is_sampled(self, is_sampled):
        """
        This should never be called in normal operation, but often is used
        for testing. We just want to make sure our sample_rate comes out correctly
        in tracestate if we set is_sampled to False.
        """
        self._is_sampled = is_sampled
        if not is_sampled:
            if self.sample_rate:
                self.sample_rate = "0"
                self.trace_parent.add_tracestate(constants.TRACESTATE.SAMPLE_RATE, self.sample_rate)

    @property
    def tracer(self) -> "Tracer":
        return self._tracer

    def track_dropped_span(self, span: SpanType):
        with self._span_timers_lock:
            try:
                resource = span.context["destination"]["service"]["resource"]
                target_type = nested_key(span.context, "service", "target", "type")
                target_name = nested_key(span.context, "service", "target", "name")
                stats = self._dropped_span_statistics[(resource, span.outcome, target_type, target_name)]
                stats["count"] += 1
                stats["duration.sum.us"] += int(span.duration.total_seconds() * 1_000_000)
            except KeyError:
                pass


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
        "dist_tracing_propagated",
        "timestamp",
        "start_time",
        "ended_time",
        "duration",
        "parent",
        "parent_span_id",
        "frames",
        "labels",
        "sync",
        "outcome",
        "_child_durations",
        "_cancelled",
    )

    def __init__(
        self,
        transaction: Transaction,
        name: str,
        span_type: str,
        context: Optional[dict] = None,
        leaf: bool = False,
        labels: Optional[dict] = None,
        parent: Optional["Span"] = None,
        parent_span_id: Optional[str] = None,
        span_subtype: Optional[str] = None,
        span_action: Optional[str] = None,
        sync: Optional[bool] = None,
        start: Optional[int] = None,
        links: Optional[Sequence[TraceParent]] = None,
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
        self.id = self.get_dist_tracing_id()
        self.transaction = transaction
        self.name = name
        self.context = context if context is not None else {}
        self.leaf = leaf
        # timestamp is bit of a mix of monotonic and non-monotonic time sources.
        # we take the (non-monotonic) transaction timestamp, and add the (monotonic) difference of span
        # start time and transaction start time. In this respect, the span timestamp is guaranteed to grow
        # monotonically with respect to the transaction timestamp
        self.parent = parent
        self.parent_span_id = parent_span_id
        self.frames = None
        self.sync = sync
        self.type = span_type
        self.subtype = span_subtype
        self.action = span_action
        self.dist_tracing_propagated = False
        self.composite: Dict[str, Any] = {}
        self._cancelled: bool = False
        super().__init__(labels=labels, start=start, links=links)
        self.timestamp = transaction.timestamp + (self.start_time - transaction.start_time)
        if self.transaction._breakdown:
            p = self.parent if self.parent else self.transaction
            p.child_started(self.start_time)

    def to_dict(self) -> dict:
        if (
            self.composite
            and self.composite["compression_strategy"] == "same_kind"
            and nested_key(self.context, "destination", "service", "resource")
        ):
            name = "Calls to " + self.context["destination"]["service"]["resource"]
        else:
            name = self.name
        result = {
            "id": self.id,
            "transaction_id": self.transaction.id,
            "trace_id": self.transaction.trace_parent.trace_id,
            # use either the explicitly set parent_span_id, or the id of the parent, or finally the transaction id
            "parent_id": self.parent_span_id or (self.parent.id if self.parent else self.transaction.id),
            "name": encoding.keyword_field(name),
            "type": encoding.keyword_field(self.type),
            "subtype": encoding.keyword_field(self.subtype),
            "action": encoding.keyword_field(self.action),
            "timestamp": int(self.timestamp * 1000000),  # microseconds
            "duration": self.duration.total_seconds() * 1000,
            "outcome": self.outcome,
        }
        if self.transaction.sample_rate is not None:
            result["sample_rate"] = float(self.transaction.sample_rate)
        if self.sync is not None:
            result["sync"] = self.sync
        if self.labels:
            if self.context is None:
                self.context = {}
            self.context["tags"] = self.labels
        if self.links:
            result["links"] = self.links
        if self.context:
            self.autofill_resource_context()
            # otel attributes and spankind need to be top-level
            if "otel_spankind" in self.context:
                result["otel"] = {"span_kind": self.context.pop("otel_spankind")}
            if self.tracer._agent.check_server_version(gte=(7, 16)):
                if "otel_attributes" in self.context:
                    if "otel" not in result:
                        result["otel"] = {"attributes": self.context.pop("otel_attributes")}
                    else:
                        result["otel"]["attributes"] = self.context.pop("otel_attributes")
            else:
                # Attributes map to labels for older versions
                attributes = self.context.pop("otel_attributes", {})
                if attributes and ("tags" not in self.context):
                    self.context["tags"] = {}
                for key, value in attributes.items():
                    self.context["tags"][key] = value
            result["context"] = self.context
        if self.frames:
            result["stacktrace"] = self.frames
        if self.composite:
            result["composite"] = {
                "compression_strategy": self.composite["compression_strategy"],
                "sum": self.composite["sum"].total_seconds() * 1000,
                "count": self.composite["count"],
            }
        return result

    def is_same_kind(self, other_span: SpanType) -> bool:
        """
        For compression purposes, two spans are considered to be of the same kind if they have the same
        values for type, subtype, and destination.service.resource
        :param other_span: another span object
        :return: bool
        """
        target_type = nested_key(self.context, "service", "target", "type")
        target_name = nested_key(self.context, "service", "target", "name")
        return bool(
            self.type == other_span.type
            and self.subtype == other_span.subtype
            and (target_type or target_name)
            and target_type == nested_key(other_span.context, "service", "target", "type")
            and target_name == nested_key(other_span.context, "service", "target", "name")
        )

    def is_exact_match(self, other_span: SpanType) -> bool:
        """
        For compression purposes, two spans are considered to be an exact match if the have the same
        name and are of the same kind.

        :param other_span: another span object
        :return: bool
        """
        return bool(self.name == other_span.name and self.is_same_kind(other_span))

    def is_compression_eligible(self) -> bool:
        """
        Determine if this span is eligible for compression.
        """
        if self.transaction.config_span_compression_enabled:
            return self.leaf and not self.dist_tracing_propagated and self.outcome in (None, constants.OUTCOME.SUCCESS)
        return False

    @property
    def discardable(self) -> bool:
        return self.leaf and not self.dist_tracing_propagated and self.outcome == constants.OUTCOME.SUCCESS

    def end(self, skip_frames: int = 0, duration: Optional[float] = None):
        """
        End this span and queue it for sending.

        :param skip_frames: amount of frames to skip from the beginning of the stack trace
        :param duration: override duration, mostly useful for testing
        :return: None
        """
        self.autofill_resource_context()
        self.autofill_service_target()
        super().end(skip_frames, duration)
        tracer = self.transaction.tracer
        if (
            tracer.span_stack_trace_min_duration >= timedelta(seconds=0)
            and self.duration >= tracer.span_stack_trace_min_duration
            and self.frames
        ):
            self.frames = tracer.frames_processing_func(self.frames)[skip_frames:]
        else:
            self.frames = None
        current_span = execution_context.get_span()
        # Because otel can detach context without ending the span, we need to
        # make sure we only unset the span if it's currently set.
        if current_span is self:
            execution_context.unset_span()

        p = self.parent if self.parent else self.transaction
        if self.transaction._breakdown:
            p._child_durations.stop(self.start_time + self.duration.total_seconds())
            self.transaction.track_span_duration(
                self.type, self.subtype, self.duration - self._child_durations.duration
            )
        p.child_ended(self)

    def report(self) -> None:
        if self.discardable and self.duration < self.transaction.config_exit_span_min_duration:
            self.transaction.track_dropped_span(self)
            self.transaction.dropped_spans += 1
        elif self._cancelled:
            self.transaction._span_counter -= 1
        else:
            self.tracer.queue_func(SPAN, self.to_dict())

    def try_to_compress(self, sibling: SpanType) -> bool:
        compression_strategy = (
            self._try_to_compress_composite(sibling) if self.composite else self._try_to_compress_regular(sibling)
        )
        if not compression_strategy:
            return False

        if not self.composite:
            self.composite = {"compression_strategy": compression_strategy, "count": 1, "sum": self.duration}
        self.composite["count"] += 1
        self.composite["sum"] += sibling.duration
        self.duration = timedelta(seconds=sibling.ended_time - self.start_time)
        self.transaction._span_counter -= 1
        return True

    def _try_to_compress_composite(self, sibling: SpanType) -> Optional[str]:
        if self.composite["compression_strategy"] == "exact_match":
            return (
                "exact_match"
                if (
                    self.is_exact_match(sibling)
                    and sibling.duration <= self.transaction.config_span_compression_exact_match_max_duration
                )
                else None
            )
        elif self.composite["compression_strategy"] == "same_kind":
            return (
                "same_kind"
                if (
                    self.is_same_kind(sibling)
                    and sibling.duration <= self.transaction.config_span_compression_same_kind_max_duration
                )
                else None
            )
        return None

    def _try_to_compress_regular(self, sibling: SpanType) -> Optional[str]:
        if not self.is_same_kind(sibling):
            return None
        if self.name == sibling.name:
            max_duration = self.transaction.config_span_compression_exact_match_max_duration
            if self.duration <= max_duration and sibling.duration <= max_duration:
                return "exact_match"
            return None
        max_duration = self.transaction.config_span_compression_same_kind_max_duration
        if self.duration <= max_duration and sibling.duration <= max_duration:
            return "same_kind"
        return None

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

    def autofill_resource_context(self):
        """Automatically fills "resource" fields based on other fields"""
        if self.context:
            resource = nested_key(self.context, "destination", "service", "resource")
            if not resource and (self.leaf or any(k in self.context for k in ("destination", "db", "message", "http"))):
                type_info = self.subtype or self.type
                instance = nested_key(self.context, "db", "instance")
                queue_name = nested_key(self.context, "message", "queue", "name")
                http_url = nested_key(self.context, "http", "url")
                if instance:
                    resource = f"{type_info}/{instance}"
                elif queue_name:
                    resource = f"{type_info}/{queue_name}"
                elif http_url:
                    resource = url_to_destination_resource(http_url)
                else:
                    resource = type_info
                if "destination" not in self.context:
                    self.context["destination"] = {}
                if "service" not in self.context["destination"]:
                    self.context["destination"]["service"] = {}
                self.context["destination"]["service"]["resource"] = resource
                # set fields that are deprecated, but still required by APM Server API
                if "name" not in self.context["destination"]["service"]:
                    self.context["destination"]["service"]["name"] = ""
                if "type" not in self.context["destination"]["service"]:
                    self.context["destination"]["service"]["type"] = ""

    def autofill_service_target(self):
        if self.leaf:
            service_target = nested_key(self.context, "service", "target") or {}

            if "type" not in service_target:  # infer type from span type & subtype
                # use sub-type if provided, fallback on type othewise
                service_target["type"] = self.subtype or self.type

            if "name" not in service_target:  # infer name from span attributes
                if nested_key(self.context, "db", "instance"):  # database spans
                    service_target["name"] = self.context["db"]["instance"]
                elif "message" in self.context:  # messaging spans
                    service_target["name"] = self.context["message"]["queue"]["name"]
                elif nested_key(self.context, "http", "url"):  # http spans
                    url = self.context["http"]["url"]
                    parsed_url = urllib.parse.urlparse(url)
                    service_target["name"] = parsed_url.hostname
                    if parsed_url.port:
                        service_target["name"] += f":{parsed_url.port}"
            if "service" not in self.context:
                self.context["service"] = {}
            self.context["service"]["target"] = service_target
        elif nested_key(self.context, "service", "target"):
            # non-exit spans should not have service.target.* fields
            del self.context["service"]["target"]

    def cancel(self) -> None:
        """
        Mark span as cancelled. Cancelled spans don't count towards started spans nor dropped spans.

        No checks are made to ensure that spans which already propagated distributed context are not
        cancelled.
        """
        self._cancelled = True

    def __str__(self):
        return "{}/{}/{}".format(self.name, self.type, self.subtype)

    @property
    def tracer(self) -> "Tracer":
        return self.transaction.tracer


class DroppedSpan(BaseSpan):
    __slots__ = ("leaf", "parent", "id", "context", "outcome", "dist_tracing_propagated")

    def __init__(self, parent, leaf=False, start=None, context=None):
        self.parent = parent
        self.leaf = leaf
        self.id = None
        self.dist_tracing_propagated = False
        self.context = context
        self.outcome = constants.OUTCOME.UNKNOWN
        super(DroppedSpan, self).__init__(start=start)

    def end(self, skip_frames: int = 0, duration: Optional[float] = None):
        super().end(skip_frames, duration)
        execution_context.unset_span()

    def child_started(self, timestamp):
        pass

    def child_ended(self, child: SpanType):
        pass

    def update_context(self, key, data):
        pass

    def report(self):
        pass

    def try_to_compress(self, sibling: SpanType) -> bool:
        return False

    def is_compression_eligible(self) -> bool:
        return False

    @property
    def name(self):
        return "DroppedSpan"

    @property
    def type(self):
        return None

    @property
    def subtype(self):
        return None

    @property
    def action(self):
        return None


class Tracer(object):
    def __init__(self, frames_collector_func, frames_processing_func, queue_func, config, agent: "elasticapm.Client"):
        self.config = config
        self.queue_func = queue_func
        self.frames_processing_func = frames_processing_func
        self.frames_collector_func = frames_collector_func
        self._agent = agent
        self._ignore_patterns = [re.compile(p) for p in config.transactions_ignore_patterns or []]

    @property
    def span_stack_trace_min_duration(self) -> timedelta:
        if self.config.span_stack_trace_min_duration != timedelta(
            seconds=0.005
        ) or self.config.span_frames_min_duration == timedelta(seconds=0.005):
            # No need to check span_frames_min_duration
            return self.config.span_stack_trace_min_duration
        else:
            # span_stack_trace_min_duration is default value and span_frames_min_duration is non-default.
            # warn and use span_frames_min_duration
            warnings.warn(
                "`span_frames_min_duration` is deprecated. Please use `span_stack_trace_min_duration`.",
                DeprecationWarning,
            )
            if self.config.span_frames_min_duration < timedelta(seconds=0):
                return timedelta(seconds=0)
            elif self.config.span_frames_min_duration == timedelta(seconds=0):
                return timedelta(seconds=-1)
            else:
                return self.config.span_frames_min_duration

    def begin_transaction(
        self,
        transaction_type: str,
        trace_parent: Optional[TraceParent] = None,
        start: Optional[float] = None,
        auto_activate: bool = True,
        links: Optional[Sequence[TraceParent]] = None,
    ) -> Transaction:
        """
        Start a new transactions and bind it in a thread-local variable

        :param transaction_type: type of the transaction, e.g. "request"
        :param trace_parent: an optional TraceParent object
        :param start: override the start timestamp, mostly useful for testing
        :param auto_activate: whether to set this transaction in execution_context
        :param links: list of traceparents to causally link this transaction to
        :returns the Transaction object
        """
        links = links if links else []
        continuation_strategy = self.config.trace_continuation_strategy

        # we restart the trace if continuation strategy is "restart", or if it is "restart_external" and our
        # "es" key is not in the tracestate header. In both cases, the original TraceParent is added to trace links.
        if trace_parent and continuation_strategy != constants.TRACE_CONTINUATION_STRATEGY.CONTINUE:
            if continuation_strategy == constants.TRACE_CONTINUATION_STRATEGY.RESTART or (
                continuation_strategy == constants.TRACE_CONTINUATION_STRATEGY.RESTART_EXTERNAL
                and not trace_parent.tracestate_dict
            ):
                links.append(trace_parent)
                trace_parent = None
        if trace_parent:
            is_sampled = bool(trace_parent.trace_options.recorded)
            sample_rate = trace_parent.tracestate_dict.get(constants.TRACESTATE.SAMPLE_RATE)
        else:
            is_sampled = (
                self.config.transaction_sample_rate == 1.0 or self.config.transaction_sample_rate > random.random()
            )
            if not is_sampled:
                sample_rate = "0"
            else:
                sample_rate = str(self.config.transaction_sample_rate)

        transaction = Transaction(
            self,
            transaction_type,
            trace_parent=trace_parent,
            is_sampled=is_sampled,
            start=start,
            sample_rate=sample_rate,
            links=links,
        )
        if trace_parent is None:
            transaction.trace_parent.add_tracestate(constants.TRACESTATE.SAMPLE_RATE, sample_rate)
        if auto_activate:
            execution_context.set_transaction(transaction)
        return transaction

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
                transaction.name = str(transaction_name) if transaction_name is not None else ""
            transaction.end(duration=duration)
            if self._should_ignore(transaction.name):
                return
            if not transaction.is_sampled and self._agent.check_server_version(gte=(8, 0)):
                return
            if transaction.result is None:
                transaction.result = result
            self.queue_func(TRANSACTION, transaction.to_dict())
        return transaction

    def _should_ignore(self, transaction_name):
        for pattern in self._ignore_patterns:
            if pattern.search(transaction_name):
                return True
        return False


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
        "links",
    )

    def __init__(
        self,
        name: Optional[str] = None,
        span_type: str = "code.custom",
        extra: Optional[dict] = None,
        skip_frames: int = 0,
        leaf: bool = False,
        labels: Optional[dict] = None,
        span_subtype: Optional[str] = None,
        span_action: Optional[str] = None,
        start: Optional[int] = None,
        duration: Optional[Union[float, timedelta]] = None,
        sync: Optional[bool] = None,
        links: Optional[Sequence[TraceParent]] = None,
    ):
        self.name = name
        if span_subtype is None and "." in span_type:
            # old style dotted type, let's split it up
            type_bits = span_type.split(".")
            if len(type_bits) == 2:
                span_type, span_subtype = type_bits[:2]
            else:
                span_type, span_subtype, span_action = type_bits[:3]
        self.type = span_type
        self.subtype = span_subtype
        self.action = span_action
        self.extra = extra
        self.skip_frames = skip_frames
        self.leaf = leaf
        self.labels = labels
        self.start = start
        if duration and not isinstance(duration, timedelta):
            duration = timedelta(seconds=duration)
        self.duration = duration
        self.sync = sync
        self.links = links

    def __call__(self, func: _AnnotatedFunctionT) -> _AnnotatedFunctionT:
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            with self:
                return func(*args, **kwds)

        return decorated

    def __enter__(self) -> Optional[SpanType]:
        return self.handle_enter(self.sync)

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        self.handle_exit(exc_type, exc_val, exc_tb)

    def handle_enter(self, sync: bool) -> Optional[SpanType]:
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
                sync=sync,
                links=self.links,
            )
        return None

    def handle_exit(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        transaction = execution_context.get_transaction()

        if transaction and transaction.is_sampled:
            try:
                outcome = "failure" if exc_val else "success"
                span = transaction.end_span(self.skip_frames, duration=self.duration, outcome=outcome)
                should_track_dropped = (
                    transaction.tracer._agent.check_server_version(gte=(7, 16)) if transaction.tracer._agent else True
                )
                if should_track_dropped and isinstance(span, DroppedSpan) and span.context:
                    transaction.track_dropped_span(span)
                if exc_val and not isinstance(span, DroppedSpan):
                    try:
                        exc_val._elastic_apm_span_id = span.id
                    except AttributeError:
                        # could happen if the exception has __slots__
                        pass
            except LookupError:
                logger.debug("ended non-existing span %s of type %s", self.name, self.type)


def label(**labels):
    """
    Labels current transaction. Keys should be strings, values can be strings, booleans,
    or numerical values (int, float, Decimal)

    :param labels: key/value map of labels
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        client = elasticapm.get_client()
        if not client or client.config.enabled:
            error_logger.warning("Ignored labels %s. No transaction currently active.", ", ".join(labels.keys()))
    else:
        transaction.label(**labels)


def set_transaction_name(name: str, override: bool = True) -> None:
    """
    Sets the name of the transaction

    :param name: the name of the transaction
    :param override: if set to False, the name is only set if no name has been set before
    :return: None
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.name is None or override:
        transaction.name = str(name)


def set_transaction_result(result, override=True):
    """
    Sets the result of the transaction. The result could be e.g. the HTTP status class (e.g "HTTP 5xx") for
    HTTP requests, or "success"/"failure" for background tasks.

    :param result: Details of the transaction result that should be set
    :param override: if set to False, the name is only set if no name has been set before
    :return: None
    """

    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if transaction.result is None or override:
        transaction.result = result


def set_transaction_outcome(outcome=None, http_status_code=None, override=True):
    """
    Set the outcome of the transaction. This should only be done at the end of a transaction
    after the outcome is determined.

    If an invalid outcome is provided, an INFO level log message will be issued.

    :param outcome: the outcome of the transaction. Allowed values are "success", "failure", "unknown". None is
                    allowed if a http_status_code is provided.
    :param http_status_code: An integer value of the HTTP status code. If provided, the outcome will be determined
                             based on the status code: Success if the status is lower than 500, failure otherwise.
                             If both a valid outcome and an http_status_code is provided, the former is used
    :param override: If set to False, the outcome will only be updated if its current value is None

    :return: None
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    if http_status_code and outcome not in constants.OUTCOME:
        try:
            http_status_code = int(http_status_code)
            outcome = constants.OUTCOME.SUCCESS if http_status_code < 500 else constants.OUTCOME.FAILURE
        except ValueError:
            logger.info('Invalid HTTP status %r provided, outcome set to "unknown"', http_status_code)
            outcome = constants.OUTCOME.UNKNOWN
    elif outcome not in constants.OUTCOME:
        logger.info('Invalid outcome %r provided, outcome set to "unknown"', outcome)
        outcome = constants.OUTCOME.UNKNOWN
    if outcome and (transaction.outcome is None or override):
        transaction.outcome = outcome


def get_transaction_id():
    """
    Returns the current transaction ID
    """
    transaction = execution_context.get_transaction()
    if not transaction:
        return
    return transaction.id


def get_trace_parent_header():
    """
    Return the trace parent header for the current transaction.
    """
    transaction = execution_context.get_transaction()
    if not transaction or not transaction.trace_parent:
        return
    return transaction.trace_parent.to_string()


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
