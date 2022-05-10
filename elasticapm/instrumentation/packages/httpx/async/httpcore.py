#  BSD 3-Clause License
#
#  Copyright (c) 2021, Elasticsearch BV
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

from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.instrumentation.packages.httpx import utils
from elasticapm.traces import DroppedSpan, execution_context
from elasticapm.utils import default_ports
from elasticapm.utils.disttracing import TracingOptions


class HTTPCoreAsyncInstrumentation(AsyncAbstractInstrumentedModule):
    """
    This instrumentation only exists to make sure we add distributed tracing
    headers on our requests from `httpx`. `httpx` is the only place this library
    is used, so no spans will actually be created (due to already being in
    a leaf span). However, the rest of the logic was left in (much of this
    mirrors the urllib3 instrumentation) in case that situation ever changes.
    """

    name = "httpcore"

    instrument_list = [
        ("httpcore._async.connection", "AsyncHTTPConnection.request"),  # < httpcore 0.11
        ("httpcore._async.connection", "AsyncHTTPConnection.arequest"),  # httpcore 0.11 - 0.12
        ("httpcore._async.connection", "AsyncHTTPConnection.handle_async_request"),  # >= httpcore 0.13
    ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        url, method, headers = utils.get_request_data(args, kwargs)
        scheme, host, port, target = url

        if port != default_ports.get(scheme):
            host += ":" + str(port)

        signature = "%s %s" % (method.upper(), host)

        url = "%s://%s%s" % (scheme, host, url)

        transaction = execution_context.get_transaction()

        async with async_capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}},
            leaf=True,
        ) as span:
            # if httpcore has been called in a leaf span, this span might be a DroppedSpan.
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            if headers is not None:
                # It's possible that there are only dropped spans, e.g. if we started dropping spans due to the
                # transaction_max_spans limit. In this case, the transaction.id is used
                parent_id = leaf_span.id if leaf_span else transaction.id
                trace_parent = transaction.trace_parent.copy_from(
                    span_id=parent_id, trace_options=TracingOptions(recorded=True)
                )
                utils.set_disttracing_headers(headers, trace_parent, transaction)
            response = await wrapped(*args, **kwargs)
            status_code = utils.get_status(response)
            if status_code:
                if span.context:
                    span.context["http"]["status_code"] = status_code
                span.set_success() if status_code < 400 else span.set_failure()
            return response

    def mutate_unsampled_call_args(self, module, method, wrapped, instance, args, kwargs, transaction):
        # since we don't have a span, we set the span id to the transaction id
        trace_parent = transaction.trace_parent.copy_from(
            span_id=transaction.id, trace_options=TracingOptions(recorded=False)
        )
        headers = utils.get_request_data(args, kwargs)[2]
        utils.set_disttracing_headers(headers, trace_parent, transaction)
        return args, kwargs
