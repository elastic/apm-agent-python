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


import logging
import typing
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence

from opentelemetry import trace as trace_api
from opentelemetry.sdk import trace as oteltrace
from opentelemetry.sdk.trace import Context, SpanKind
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.util import types

import elasticapm
from elasticapm.traces import execution_context

from .span import Span

logger = logging.getLogger("elasticapm.otel")


class Tracer(oteltrace.Tracer):
    """
    Handles span creation and in-process context propagation.
    This class provides methods for manipulating the context, creating spans,
    and controlling spans' lifecycles.
    """

    def start_span(
        self,
        name: str,
        context: Optional[Context] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: Optional[Sequence[Any]] = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> "Span":
        """
        Starts a span.
        Create a new span. Start the span without setting it as the current
        span in the context. To start the span and use the context in a single
        method, see :meth:`start_as_current_span`.
        By default the current span in the context will be used as parent, but an
        explicit context can also be specified, by passing in a `Context` containing
        a current `Span`. If there is no current span in the global `Context` or in
        the specified context, the created span will be a root span.
        The span can be used as a context manager. On exiting the context manager,
        the span's end() method will be called.
        Example::
            # trace.get_current_span() will be used as the implicit parent.
            # If none is found, the created span will be a root instance.
            with tracer.start_span("one") as child:
                child.add_event("child's event")
        Args:
            name: The name of the span to be created.
            context: An optional Context containing the span's parent. Defaults to the
                global context.
            kind: The span's kind (relationship to parent). Note that is
                meaningful even if there is no parent.
            attributes: The span's attributes.
            links: Links span to other spans
            start_time: Sets the start time of a span
            record_exception: Whether to record any exceptions raised within the
                context as error event on the span.
            set_status_on_exception: Only relevant if the returned span is used
                in a with/context manager. Defines wether the span status will
                be automatically set to ERROR when an uncaught exception is
                raised in the span with block. The span status won't be set by
                this mechanism if it was previously set manually.
        Returns:
            The newly-created span.
        """
        if links:
            logger.warning("The opentelemetry bridge does not support links at this time.")
        if not record_exception:
            logger.warning("record_exception was set to False, but exceptions will still be recorded for this span.")

        parent_span_context = trace_api.get_current_span(context).get_span_context()

        if parent_span_context is not None and not isinstance(parent_span_context, trace_api.SpanContext):
            raise TypeError("parent_span_context must be a SpanContext or None.")

        trace_id = None
        if parent_span_context and parent_span_context.is_valid:
            trace_id = parent_span_context.trace_id
            # FIXME tracestate from remote context too?

        span = None
        current_transaction = execution_context.get_transaction()
        if parent_span_context and current_transaction:
            logger.warning(
                "Remote context included when a transaction was already active. "
                "Ignoring remote context and creating a Span instead."
            )
        elif parent_span_context:
            # FIXME Create a transaction with trace_id from parent_span_context
            trace_id
            pass
        elif not current_transaction:
            # FIXME Create root transaction
            pass
        else:
            elastic_span = current_transaction.begin_span(name, start=start_time)
            span = Span(elastic_span=elastic_span)
            span.set_attributes(attributes)
            # FIXME set SpanKind
            # FIXME deal with set_status_on_exception

        return span

    @contextmanager  # type: ignore
    def start_as_current_span(
        self,
        name: str,
        context: Optional[Context] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: types.Attributes = None,
        links: Optional[Sequence[Any]] = None,
        start_time: Optional[int] = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Iterator["Span"]:
        """
        Context manager for creating a new span and set it
        as the current span in this tracer's context.
        Exiting the context manager will call the span's end method,
        as well as return the current span to its previous value by
        returning to the previous context.
        Example::
            with tracer.start_as_current_span("one") as parent:
                parent.add_event("parent's event")
                with trace.start_as_current_span("two") as child:
                    child.add_event("child's event")
                    trace.get_current_span()  # returns child
                trace.get_current_span()      # returns parent
            trace.get_current_span()          # returns previously active span
        This is a convenience method for creating spans attached to the
        tracer's context. Applications that need more control over the span
        lifetime should use :meth:`start_span` instead. For example::
            with tracer.start_as_current_span(name) as span:
                do_work()
        is equivalent to::
            span = tracer.start_span(name)
            with opentelemetry.trace.use_span(span, end_on_exit=True):
                do_work()
        Args:
            name: The name of the span to be created.
            context: An optional Context containing the span's parent. Defaults to the
                global context.
            kind: The span's kind (relationship to parent). Note that is
                meaningful even if there is no parent.
            attributes: The span's attributes.
            links: Links span to other spans
            start_time: Sets the start time of a span
            record_exception: Whether to record any exceptions raised within the
                context as error event on the span.
            set_status_on_exception: Only relevant if the returned span is used
                in a with/context manager. Defines wether the span status will
                be automatically set to ERROR when an uncaught exception is
                raised in the span with block. The span status won't be set by
                this mechanism if it was previously set manually.
            end_on_exit: Whether to end the span automatically when leaving the
                context manager.
        Yields:
            The newly-created span.
        """
        # FIXME
        raise NotImplementedError()


def get_tracer(
    instrumenting_module_name: str,
    instrumenting_library_version: typing.Optional[str] = None,
    tracer_provider: Optional[Any] = None,
    schema_url: Optional[str] = None,
) -> "Tracer":
    """
    Returns the Elastic-wrapped Tracer object which allows for span creation

    Args:
        instrumenting_module_name:  The name of the instrumenting module
            (usually just `__name__`)

    All other args are ignored in this implementation.
    """
    return Tracer(instrumenting_module_name)


def set_tracer_provider(tracer_provider: Any) -> None:
    """
    No-op to match opentelemetry's `trace` module
    """
    return None


def get_tracer_provider() -> None:
    """
    Not implemented by otel bridge
    """
    raise NotImplementedError()


@contextmanager
def use_span(
    span: Span,
    end_on_exit: bool = False,
    record_exception: bool = True,
    set_status_on_exception: bool = True,
) -> None:
    """
    Takes a non-active span and activates it in the current context.
    """
    execution_context.set_span(span)
    try:
        yield span
    except Exception as exc:
        if record_exception:
            elasticapm.get_client().capture_exception(handled=False)
        if set_status_on_exception:
            span.set_status(
                Status(
                    status_code=StatusCode.ERROR,
                    description=f"{type(exc).__name__}: {exc}",
                )
            )
    finally:
        execution_context.unset_span()
        if end_on_exit:
            span.end()
