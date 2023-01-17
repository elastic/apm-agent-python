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

import elasticapm
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.instrumentation.packages.elasticsearch import (
    ElasticsearchConnectionInstrumentation,
    ElasticsearchTransportInstrumentation,
)
from elasticapm.traces import DroppedSpan, execution_context


class ElasticSearchAsyncConnection(ElasticsearchConnectionInstrumentation, AsyncAbstractInstrumentedModule):
    name = "elasticsearch_connection"

    def get_instrument_list(self):
        try:
            import elastic_transport  # noqa: F401

            return [
                ("elastic_transport._node._http_aiohttp", "AiohttpHttpNode.perform_request"),
            ]
        except ImportError:
            return [
                ("elasticsearch_async.connection", "AIOHttpConnection.perform_request"),
                ("elasticsearch._async.http_aiohttp", "AIOHttpConnection.perform_request"),
            ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        span = execution_context.get_span()
        if not span or isinstance(span, DroppedSpan):
            return await wrapped(*args, **kwargs)

        self._update_context_by_request_data(span.context, instance, args, kwargs)

        result = await wrapped(*args, **kwargs)
        if hasattr(result, "meta"):  # elasticsearch-py 8.x+
            status_code = result.meta.status
        else:
            status_code = result[0]

        span.context["http"] = {"status_code": status_code}

        return result


class ElasticsearchAsyncTransportInstrumentation(
    ElasticsearchTransportInstrumentation, AsyncAbstractInstrumentedModule
):
    name = "elasticsearch_connection"

    instrument_list = [
        ("elasticsearch._async.transport", "AsyncTransport.perform_request"),
    ]

    def get_instrument_list(self):
        try:
            import elastic_transport  # noqa: F401

            return [
                ("elastic_transport", "AsyncTransport.perform_request"),
            ]
        except ImportError:
            return [
                ("elasticsearch._async.transport", "AsyncTransport.perform_request"),
            ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        async with elasticapm.async_capture_span(
            self._get_signature(args, kwargs),
            span_type="db",
            span_subtype="elasticsearch",
            span_action="query",
            extra={},
            skip_frames=2,
            leaf=True,
        ) as span:
            result_data = await wrapped(*args, **kwargs)

            hits = self._get_hits(result_data)
            if hits:
                span.context["db"]["rows_affected"] = hits

            return result_data
