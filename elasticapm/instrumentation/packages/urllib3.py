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

import itertools

from elasticapm.conf import constants
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, capture_span, execution_context
from elasticapm.utils import default_ports, url_to_destination
from elasticapm.utils.disttracing import TracingOptions


def _set_disttracing_headers(headers, trace_parent, transaction):
    trace_parent_str = trace_parent.to_string()
    headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent_str
    if transaction.tracer.config.use_elastic_traceparent_header:
        headers[constants.TRACEPARENT_LEGACY_HEADER_NAME] = trace_parent_str
    if trace_parent.tracestate:
        headers[constants.TRACESTATE_HEADER_NAME] = trace_parent.tracestate


def update_headers(args, kwargs, instance, transaction, trace_parent):
    """
    The headers might be in 3 different places: as 4th positional argument, as "headers" keyword argument,
    or, if none of the former two are provided, as instance variable on the HTTPConnection object.

    If the headers are in the positional arguments tuple, a new tuple with updated headers will be returned.
    If they are in the keyword arguments or on the instance, an updated kwargs dict will be returned

    :param args: list of positional arguments
    :param kwargs: dict of keyword arguments
    :param instance: the HTTPConnection instance
    :param transaction: the Transaction object
    :param trace_parent: the TraceParent object
    :return: an (args, kwargs) tuple
    """
    if len(args) >= 4 and args[3]:
        headers = args[3].copy()
        args = tuple(itertools.chain((args[:3]), (headers,), args[4:]))
    elif "headers" in kwargs and kwargs["headers"]:
        headers = kwargs["headers"].copy()
        kwargs["headers"] = headers
    else:
        headers = instance.headers.copy() if instance.headers else {}
        # we don't want to change the instance headers, so we'll cheat and
        # set the headers as keywords. This slightly changes how the wrapped
        # method is called compared to uninstrumented code.
        kwargs["headers"] = headers
    _set_disttracing_headers(headers, trace_parent, transaction)
    return args, kwargs


class Urllib3Instrumentation(AbstractInstrumentedModule):
    name = "urllib3"

    instrument_list = [
        ("urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
        # packages that vendor or vendored urllib3 in the past
        ("requests.packages.urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
        ("botocore.vendored.requests.packages.urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "method" in kwargs:
            method = kwargs["method"]
        else:
            method = args[0]

        host = instance.host

        if instance.port != default_ports.get(instance.scheme):
            host += ":" + str(instance.port)

        if "url" in kwargs:
            url = kwargs["url"]
        else:
            url = args[1]

        signature = method.upper() + " " + host

        url = "%s://%s%s" % (instance.scheme, host, url)
        destination = url_to_destination(url)

        transaction = execution_context.get_transaction()

        with capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            # if urllib3 has been called in a leaf span, this span might be a DroppedSpan.
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            parent_id = leaf_span.id if leaf_span else transaction.id
            trace_parent = transaction.trace_parent.copy_from(
                span_id=parent_id, trace_options=TracingOptions(recorded=True)
            )
            args, kwargs = update_headers(args, kwargs, instance, transaction, trace_parent)
            response = wrapped(*args, **kwargs)
            if response:
                if span.context:
                    span.context["http"]["status_code"] = response.status
                span.set_success() if response.status < 400 else span.set_failure()
            return response

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )
        return update_headers(args, kwargs, instance, transaction, trace_parent)
