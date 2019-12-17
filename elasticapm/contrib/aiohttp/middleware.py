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

import aiohttp
from aiohttp.web import middleware

import elasticapm
from elasticapm.contrib.aiohttp.utils import get_data_from_request, get_data_from_response
from elasticapm.utils.disttracing import TraceParent


class AioHttpTraceParent(TraceParent):
    @classmethod
    def merge_duplicate_headers(cls, headers, key):
        return ",".join(headers.getall(key, [])) or None


def tracing_middleware(app):
    from elasticapm.contrib.aiohttp import CLIENT_KEY  # noqa

    async def handle_request(request, handler):
        elasticapm_client = app.get(CLIENT_KEY)
        if elasticapm_client:
            request[CLIENT_KEY] = elasticapm_client
            trace_parent = AioHttpTraceParent.from_headers(request.headers)
            elasticapm_client.begin_transaction("request", trace_parent=trace_parent)
            resource = request.match_info.route.resource
            name = request.method
            if resource:
                # canonical has been added in 3.3, and returns one of path, formatter, prefix
                for attr in ("canonical", "_path", "_formatter", "_prefix"):
                    if hasattr(resource, attr):
                        name += " " + getattr(resource, attr)
                        break
                else:
                    name += " unknown route"
            else:
                name += " unknown route"
            elasticapm.set_transaction_name(name, override=False)
            elasticapm.set_context(
                lambda: get_data_from_request(
                    request,
                    capture_body=elasticapm_client.config.capture_body in ("transactions", "all"),
                    capture_headers=elasticapm_client.config.capture_headers,
                ),
                "request",
            )

        try:
            response = await handler(request)
            elasticapm.set_transaction_result("HTTP {}xx".format(response.status // 100), override=False)
            elasticapm.set_context(
                lambda: get_data_from_response(response, capture_headers=elasticapm_client.config.capture_headers),
                "response",
            )
            return response
        except Exception:
            if elasticapm_client:
                elasticapm_client.capture_exception(
                    context={
                        "request": get_data_from_request(
                            request, capture_body=elasticapm_client.config.capture_body in ("all", "errors")
                        )
                    }
                )
                elasticapm.set_transaction_result("HTTP 5xx", override=False)
                elasticapm.set_context({"status_code": 500}, "response")
            raise
        finally:
            elasticapm_client.end_transaction()

    # decorating with @middleware is only required in aiohttp < 4.0, and we only support 3+
    if aiohttp.__version__.startswith("3"):
        return middleware(handle_request)
    return handle_request
