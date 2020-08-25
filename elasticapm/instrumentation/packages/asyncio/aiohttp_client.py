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

from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, execution_context
from elasticapm.utils import get_host_from_url, sanitize_url, url_to_destination
from elasticapm.utils.disttracing import TracingOptions


class AioHttpClientInstrumentation(AsyncAbstractInstrumentedModule):
    name = "aiohttp_client"

    instrument_list = [("aiohttp.client", "ClientSession._request")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        method = kwargs["method"] if "method" in kwargs else args[0]
        url = kwargs["url"] if "url" in kwargs else args[1]
        url = str(url)
        destination = url_to_destination(url)

        signature = " ".join([method.upper(), get_host_from_url(url)])
        url = sanitize_url(url)
        transaction = execution_context.get_transaction()

        async with async_capture_span(
            signature,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            leaf_span = span
            while isinstance(leaf_span, DroppedSpan):
                leaf_span = leaf_span.parent

            parent_id = leaf_span.id if leaf_span else transaction.id
            trace_parent = transaction.trace_parent.copy_from(
                span_id=parent_id, trace_options=TracingOptions(recorded=True)
            )
            headers = kwargs.get("headers") or {}
            self._set_disttracing_headers(headers, trace_parent, transaction)
            kwargs["headers"] = headers
            response = await wrapped(*args, **kwargs)
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

        headers = kwargs.get("headers") or {}
        self._set_disttracing_headers(headers, trace_parent, transaction)
        kwargs["headers"] = headers
        return args, kwargs

    def _set_disttracing_headers(self, headers, trace_parent, transaction):
        trace_parent_str = trace_parent.to_string()
        headers[constants.TRACEPARENT_HEADER_NAME] = trace_parent_str
        if transaction.tracer.config.use_elastic_traceparent_header:
            headers[constants.TRACEPARENT_LEGACY_HEADER_NAME] = trace_parent_str
        if trace_parent.tracestate:
            headers[constants.TRACESTATE_HEADER_NAME] = trace_parent.tracestate
