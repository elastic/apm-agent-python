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

import types as python_types
import typing

from opentelemetry import trace as oteltrace
from opentelemetry.trace.span import SpanContext
from opentelemetry.trace.status import Status
from opentelemetry.util import types


class Span(oteltrace.Span):
    """A span represents a single operation within a trace."""

    def end(self, end_time: typing.Optional[int] = None) -> None:
        """Sets the current time as the span's end time.
        The span's end time is the wall time at which the operation finished.
        Only the first call to `end` should modify the span, and
        implementations are free to ignore or raise on further calls.
        """

    def get_span_context(self) -> "SpanContext":
        """Gets the span's SpanContext.
        Get an immutable, serializable identifier for this span that can be
        used to create new child spans.
        Returns:
            A :class:`opentelemetry.trace.SpanContext` with a copy of this span's immutable state.
        """

    def set_attributes(self, attributes: typing.Dict[str, types.AttributeValue]) -> None:
        """Sets Attributes.
        Sets Attributes with the key and value passed as arguments dict.
        Note: The behavior of `None` value attributes is undefined, and hence strongly discouraged.
        """

    def set_attribute(self, key: str, value: types.AttributeValue) -> None:
        """Sets an Attribute.
        Sets a single Attribute with the key and value passed as arguments.
        Note: The behavior of `None` value attributes is undefined, and hence strongly discouraged.
        """

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

    def update_name(self, name: str) -> None:
        """Updates the `Span` name.
        This will override the name provided via :func:`opentelemetry.trace.Tracer.start_span`.
        Upon this update, any sampling behavior based on Span name will depend
        on the implementation.
        """

    def is_recording(self) -> bool:
        """Returns whether this span will be recorded.
        Returns true if this Span is active and recording information like
        events with the add_event operation and attributes using set_attribute.
        """

    def set_status(self, status: Status) -> None:
        """Sets the Status of the Span. If used, this will override the default
        Span status.
        """

    def record_exception(
        self,
        exception: Exception,
        attributes: types.Attributes = None,
        timestamp: typing.Optional[int] = None,
        escaped: bool = False,
    ) -> None:
        """Records an exception as a span event."""

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
