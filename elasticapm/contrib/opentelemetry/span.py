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

import datetime
import types as python_types
import typing

# FIXME try:except these imports
from opentelemetry.sdk import trace as oteltrace
from opentelemetry.trace.span import SpanContext
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.util import types

import elasticapm
import elasticapm.conf.constants as constants
import elasticapm.traces
from elasticapm.traces import execution_context


class Span(oteltrace.Span):
    """
    This is a wrapper around an Elastic APM Span/Transaction object, to match the
    otel Span API
    """

    def __init__(self, elastic_span: elasticapm.traces.BaseSpan):
        self.elastic_span = elastic_span
        elastic_span.otel_wrapper = self

    def end(self, end_time: typing.Optional[int] = None) -> None:
        """Sets the current time as the span's end time.
        The span's end time is the wall time at which the operation finished.
        Only the first call to `end` should modify the span, and
        implementations are free to ignore or raise on further calls.
        """
        if self.elastic_span.ended_time:
            # Already ended
            return
        if end_time:
            # FIXME calculate duration
            self.elastic_span.end()
        else:
            self.elastic_span.end()
        if isinstance(self.elastic_span, elasticapm.traces.Transaction):
            # Transactions don't auto-clear when they end
            execution_context.get_transaction(clear=True)

    def get_span_context(self) -> "SpanContext":
        """Gets the span's SpanContext.
        Get an immutable, serializable identifier for this span that can be
        used to create new child spans.
        Returns:
            A :class:`opentelemetry.trace.SpanContext` with a copy of this span's immutable state.
        """
        # FIXME trace_options and trace_state
        return SpanContext(
            trace_id=int(self.elastic_span.transaction.trace_parent.trace_id, base=16),
            span_id=int(self.elastic_span.id, base=16),
            is_remote=False,
        )

    def set_attributes(self, attributes: typing.Dict[str, types.AttributeValue]) -> None:
        """Sets Attributes.
        Sets Attributes with the key and value passed as arguments dict.
        Note: The behavior of `None` value attributes is undefined, and hence strongly discouraged.
        """
        if not attributes:
            return
        for key, value in attributes.items():
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        """Sets an Attribute.
        Sets a single Attribute with the key and value passed as arguments.
        Note: The behavior of `None` value attributes is undefined, and hence strongly discouraged.
        """
        # FIXME need to handle otel_attributes -> top level `otel` in the to_dict() methods on Transaction/Span
        if "otel_attributes" not in self.elastic_span.context:
            self.elastic_span.context["otel_attributes"] = {}
        self.elastic_span.context["otel_attributes"][key] = value

    def add_event(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: typing.Optional[int] = None,
    ) -> None:
        """Adds an `Event`.
        Adds a single `Event` with the name and, optionally, a timestamp and
        attributes passed as arguments. Implementations should generate a
        timestamp if the `timestamp` argument is omitted.
        """
        raise NotImplementedError("Events are not implemented in the otel bridge at this time")

    def update_name(self, name: str) -> None:
        """Updates the `Span` name.
        This will override the name provided via :func:`opentelemetry.trace.Tracer.start_span`.
        Upon this update, any sampling behavior based on Span name will depend
        on the implementation.
        """
        self.elastic_span.name = name

    def is_recording(self) -> bool:
        """Returns whether this span will be recorded.
        Returns true if this Span is active and recording information like
        events with the add_event operation and attributes using set_attribute.
        """
        self.elastic_span.transaction.is_sampled

    def set_status(self, status: Status) -> None:
        """Sets the Status of the Span. If used, this will override the default
        Span status.
        """
        if status.status_code == StatusCode.ERROR:
            self.elastic_span.outcome = constants.OUTCOME.FAILURE
        elif status.status_code == StatusCode.OK:
            self.elastic_span.outcome = constants.OUTCOME.SUCCESS
        else:
            self.elastic_span.outcome = constants.OUTCOME.UNKNOWN

    def record_exception(
        self,
        exception: Exception,
        attributes: types.Attributes = None,
        timestamp: typing.Optional[int] = None,
        escaped: bool = False,
    ) -> None:
        """Records an exception as a span event."""
        client = elasticapm.get_client()
        # FIXME should otel_attributes be top-level on the exception object?
        client.capture_exception(
            exc_info=(type(exception), exception, exception.__traceback__),
            date=datetime.datetime.fromtimestamp(timestamp),
            context={"otel_attributes": attributes},
            handled=escaped,
        )

    def __enter__(self) -> "Span":
        """Invoked when `Span` is used as a context manager.
        Returns the `Span` itself.
        """
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_val: typing.Optional[BaseException],
        exc_tb: typing.Optional[python_types.TracebackType],
    ) -> None:
        """Ends context manager and calls `end` on the `Span`."""

        self.end()
