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
import uuid

from opentelemetry.context import Context
from opentelemetry.trace.propagation import _SPAN_KEY

from elasticapm.contrib.opentelemetry.span import Span as OtelSpan
from elasticapm.traces import Transaction, execution_context

logger = logging.getLogger("elasticapm.otel")


def create_key(keyname: str) -> str:
    """To allow cross-cutting concern to control access to their local state,
    the RuntimeContext API provides a function which takes a keyname as input,
    and returns a unique key.
    Args:
        keyname: The key name is for debugging purposes and is not required to be unique.
    Returns:
        A unique string representing the newly created key.
    """
    return keyname + "-" + str(uuid.uuid4())


def get_value(key: str, context: typing.Optional[Context] = None) -> "object":
    """To access the local state of a concern, the RuntimeContext API
    provides a function which takes a context and a key as input,
    and returns a value.
    Args:
        key: The key of the value to retrieve.
        context: The context from which to retrieve the value, if None, the current context is used.
    Returns:
        The value associated with the key.
    """
    return context.get(key) if context is not None else get_current().get(key)


def set_value(key: str, value: "object", context: typing.Optional[Context] = None) -> Context:
    """To record the local state of a cross-cutting concern, the
    RuntimeContext API provides a function which takes a context, a
    key, and a value as input, and returns an updated context
    which contains the new value.
    Args:
        key: The key of the entry to set.
        value: The value of the entry to set.
        context: The context to copy, if None, the current context is used.
    Returns:
        A new `Context` containing the value set.
    """
    if context is None:
        context = get_current()
    new_values = context.copy()
    new_values[key] = value
    return Context(new_values)


def get_current() -> Context:
    """To access the context associated with program execution,
    the Context API provides a function which takes no arguments
    and returns a Context.

    Returns:
        The current `Context` object.
    """
    span = execution_context.get_span()
    if not span:
        span = execution_context.get_transaction()
    if not span:
        return Context()

    otel_span = getattr(span, "otel_wrapper", OtelSpan(span.name, span))
    context = otel_span.otel_context

    return context


def attach(context: Context) -> object:
    """Associates a Context with the caller's current execution unit.

    Due to limitations in the Elastic APM context management, a token is not
    returned by this method, nor required to detach() a Context later.

    Note that a Context will not be attached if it doesn't have an OtelSpan at _SPAN_KEY

    Args:
        context: The Context to set as current.
    Returns:
        None
    """
    span = context.get(_SPAN_KEY)
    if not span:
        logger.error("Attempted to attach a context without a valid OtelSpan")
        return None
    span.otel_context = context
    elastic_span = span.elastic_span
    if isinstance(elastic_span, Transaction):
        execution_context.set_transaction(elastic_span)
    else:
        execution_context.set_span(elastic_span)

    return None


def detach(token: typing.Optional[object] = None) -> None:
    """Resets the Context associated with the caller's current execution unit
    to the value it had before attaching a specified Context.

    Due to limitations in the Elastic APM context management, a token is not
    returned by attach(), nor required to detach() a Context later.

    Args:
        token: Tokens are not supported in this bridge, this argument is unused
    """
    if execution_context.get_span():
        execution_context.unset_span()
    else:
        logger.warning("Can't detach a running transaction. Please end the transaction instead.")
