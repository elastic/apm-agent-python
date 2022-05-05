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
import urllib.parse
from typing import Optional

from opentelemetry.context import Context
from opentelemetry.sdk import trace as oteltrace
from opentelemetry.trace import SpanKind
from opentelemetry.trace.propagation import _SPAN_KEY
from opentelemetry.trace.span import SpanContext, TraceFlags, TraceState
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.util import types

import elasticapm
import elasticapm.conf.constants as constants
import elasticapm.traces


class Span(oteltrace.Span):
    """
    This is a wrapper around an Elastic APM Span/Transaction object, to match the
    otel Span API
    """

    def __init__(
        self,
        name: str,
        elastic_span: elasticapm.traces.BaseSpan,
        set_status_on_exception: Optional[bool] = None,
        client: Optional[elasticapm.Client] = None,
    ):
        self.elastic_span = elastic_span
        self.otel_context = Context({_SPAN_KEY: self})
        elastic_span.otel_wrapper = self
        self.set_status_on_exception = set_status_on_exception
        self.client = client if client else elasticapm.get_client()
        self._name = name

    def end(self, end_time: Optional[int] = None) -> None:
        """Sets the current time as the span's end time.
        The span's end time is the wall time at which the operation finished.
        Only the first call to `end` should modify the span, and
        implementations are free to ignore or raise on further calls.
        """
        is_transaction = isinstance(self.elastic_span, elasticapm.traces.Transaction)
        if self.elastic_span.ended_time:
            # Already ended
            return
        self._set_types()
        if end_time:
            if is_transaction:
                self.client.end_transaction(
                    name=self._name,
                    result=self.elastic_span.outcome or "OK",
                    duration=end_time - self.elastic_span.timestamp,
                )
            else:
                self.elastic_span.end(duration=end_time - self.elastic_span.timestamp)
        else:
            if is_transaction:
                self.client.end_transaction(name=self._name, result=self.elastic_span.outcome or "OK")
            else:
                self.elastic_span.end()

    def get_span_context(self) -> "SpanContext":
        """Gets the span's SpanContext.
        Get an immutable, serializable identifier for this span that can be
        used to create new child spans.
        Returns:
            A :class:`opentelemetry.trace.SpanContext` with a copy of this span's immutable state.
        """
        return SpanContext(
            trace_id=int(self.elastic_span.transaction.trace_parent.trace_id, base=16),
            span_id=int(self.elastic_span.id, base=16),
            is_remote=False,
            trace_flags=TraceFlags(
                TraceFlags.SAMPLED if self.elastic_span.transaction.is_sampled else TraceFlags.DEFAULT
            ),
            trace_state=TraceState(list(self.elastic_span.transaction.trace_parent.tracestate_dict.items())),
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
        if "otel_attributes" not in self.elastic_span.context:
            self.elastic_span.context["otel_attributes"] = {}
        self.elastic_span.context["otel_attributes"][key] = value

    def add_event(
        self,
        name: str,
        attributes: types.Attributes = None,
        timestamp: Optional[int] = None,
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
        return self.elastic_span.transaction.is_sampled and not self.elastic_span.ended_time

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
        timestamp: Optional[int] = None,
        escaped: bool = False,
    ) -> None:
        """Records an exception as a span event."""
        client = elasticapm.get_client()
        client.capture_exception(
            exc_info=(type(exception), exception, exception.__traceback__),
            date=datetime.datetime.fromtimestamp(timestamp),
            context={"otel_attributes": attributes} if attributes else None,
            handled=escaped,
        )

    def __enter__(self) -> "Span":
        """Invoked when `Span` is used as a context manager.
        Returns the `Span` itself.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[typing.Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[python_types.TracebackType],
    ) -> None:
        """Ends context manager and calls `end` on the `Span`."""

        self.end()

    def _set_types(self):
        """
        Set the types and subtypes for the underlying Elastic transaction/span
        """
        if isinstance(self.elastic_span, elasticapm.traces.Transaction):
            attributes = self.elastic_span.context.get("otel_attributes", {})
            span_kind = self.elastic_span.context["otel_spankind"]
            is_rpc = bool(attributes.get("rpc.system"))
            is_http = bool(attributes.get("http.url")) or bool(attributes.get("http.scheme"))
            is_messaging = bool(attributes.get("messaging.system"))
            if span_kind == SpanKind.SERVER.name and (is_rpc or is_http):
                transaction_type = "request"
            elif span_kind == SpanKind.CONSUMER.name and is_messaging:
                transaction_type = "messaging"
            else:
                transaction_type = "unknown"
            self.elastic_span.transaction_type = transaction_type
        else:
            attributes = self.elastic_span.context.get("otel_attributes", {})
            span_type = None
            span_subtype = None
            resource = None

            def http_port_from_scheme(scheme: str):
                if scheme == "http":
                    return 80
                elif scheme == "https":
                    return 443
                return None

            def parse_net_name(url: str):
                u = urllib.parse.urlparse(url)
                if u.port:
                    return u.netloc
                else:
                    port = http_port_from_scheme(u.scheme)
                    return u.netloc if not port else "{}:{}".format(u.netloc, port)

            net_port = attributes.get("net.peer.port", -1)
            net_name = net_peer = attributes.get("net.peer.name", attributes.get("net.peer.ip", ""))

            if net_name and (net_port > 0):
                net_name = f"{net_name}:{net_port}"

            if attributes.get("db.system"):
                span_type = "db"
                span_subtype = attributes.get("db.system")
                resource = net_name or span_subtype
                if attributes.get("db.name"):
                    resource = "{}/{}".format(resource, attributes.get("db.name"))
            elif attributes.get("messaging.system"):
                span_type = "messaging"
                span_subtype = attributes.get("messaging.system")
                if not net_name and attributes.get("messaging.url"):
                    net_name = parse_net_name(attributes.get("messaging.url"))
                resource = net_name or span_subtype
                if attributes.get("messaging.destination"):
                    resource = "{}/{}".format(resource, attributes.get("messaging.destination"))
            elif attributes.get("rpc.system"):
                span_type = "external"
                span_subtype = attributes.get("rpc.system")
                resource = net_name or span_subtype
                if attributes.get("rpc.service"):
                    resource = "{}/{}".format(resource, attributes.get("rpc.service"))
            elif attributes.get("http.url") or attributes.get("http.scheme"):
                span_type = "external"
                span_subtype = "http"
                http_host = attributes.get("http.host", net_peer)
                if http_host:
                    if net_port < 0:
                        net_port = http_port_from_scheme(attributes.get("http.scheme"))
                    resource = http_host if net_port < 0 else f"{http_host}:{net_port}"
                elif attributes.get("http.url"):
                    resource = parse_net_name(attributes["http.url"])

            if not span_type:
                span_kind = self.elastic_span.context["otel_spankind"]
                if span_kind == SpanKind.INTERNAL.name:
                    span_type = "app"
                    span_subtype = "internal"
                else:
                    span_type = "unknown"
            self.elastic_span.type = span_type
            self.elastic_span.subtype = span_subtype
            if resource:
                if "destination" not in self.elastic_span.context:
                    self.elastic_span.context["destination"] = {"service": {"resource": resource}}
                elif "service" not in self.elastic_span.context["destination"]:
                    self.elastic_span.context["destination"]["service"] = {"resource": resource}
                else:
                    self.elastic_span.context["destination"]["service"]["resource"] = resource
