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

from aiohttp.web import middleware

import elasticapm
from elasticapm.conf import constants
from elasticapm.contrib.aiohttp.utils import get_data_from_request, get_data_from_response
from elasticapm.utils.disttracing import TraceParent


def tracing_middleware(app):
    from elasticapm.contrib.aiohttp import CLIENT_KEY  # noqa

    @middleware
    async def handle_request(request, handler):
        elasticapm_client = app.get(CLIENT_KEY)
        if elasticapm_client:
            request[CLIENT_KEY] = elasticapm_client
            if constants.TRACEPARENT_HEADER_NAME in request.headers:
                trace_parent = TraceParent.from_string(request.headers[constants.TRACEPARENT_HEADER_NAME])
            else:
                trace_parent = None
            elasticapm_client.begin_transaction("request", trace_parent=trace_parent)

        try:
            response = await handler(request)
            status = "HTTP {}xx".format(response.status // 100)
            resource = request.match_info.route.resource
            if resource:
                name = "{} {}".format(request.method, resource.canonical)
            else:
                name = "unkown route"
            elasticapm.set_context(
                lambda: get_data_from_request(
                    request,
                    capture_body=elasticapm_client.config.capture_body in ("transactions", "all"),
                    capture_headers=elasticapm_client.config.capture_headers,
                ),
                "request",
            )
            elasticapm.set_context(
                lambda: get_data_from_response(response, capture_headers=elasticapm_client.config.capture_headers),
                "response",
            )
            elasticapm_client.end_transaction(name, status)
            return response
        except Exception:
            if elasticapm_client:
                elasticapm_client.capture_exception()
            raise

    return handle_request
