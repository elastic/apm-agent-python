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
from aiohttp.web import HTTPException, middleware

import elasticapm
from elasticapm import get_client
from elasticapm.conf import constants
from elasticapm.contrib.aiohttp.utils import get_data_from_request, get_data_from_response
from elasticapm.utils.disttracing import TraceParent


class AioHttpTraceParent(TraceParent):
    @classmethod
    def merge_duplicate_headers(cls, headers, key):
        return ",".join(headers.getall(key, [])) or None


def tracing_middleware(app, client=None):
    async def handle_request(request, handler):
        elasticapm_client = get_client() if client is None else client
        should_trace = elasticapm_client and not elasticapm_client.should_ignore_url(request.path)
        if should_trace:
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
                lambda: get_data_from_request(request, elasticapm_client.config, constants.TRANSACTION), "request"
            )

        try:
            response = await handler(request)
            if should_trace:
                elasticapm.set_transaction_result("HTTP {}xx".format(response.status // 100), override=False)
                elasticapm.set_transaction_outcome(http_status_code=response.status, override=False)
                elasticapm.set_context(
                    lambda: get_data_from_response(response, elasticapm_client.config, constants.TRANSACTION),
                    "response",
                )
            return response
        except HTTPException as exc:
            # HTTPExceptions are response-like, e.g. have headers and status code. They can represent an HTTP
            # response below a 500 status code and therefore not something to capture as exception. Like
            # HTTPOk can be raised but will most likely be wrongly tagged as an APM error. Let's try and
            # capture this according to the status.
            if exc.status_code < 500 and not should_trace:
                raise
            if elasticapm_client:
                elasticapm.set_transaction_result("HTTP {}xx".format(exc.status_code // 100), override=False)
                elasticapm.set_transaction_outcome(http_status_code=exc.status_code, override=False)
                elasticapm.set_context(
                    lambda: get_data_from_response(
                        exc,  # noqa: F821
                        elasticapm_client.config,
                        constants.ERROR if exc.status_code >= 500 else constants.TRANSACTION,  # noqa: F821
                    ),
                    "response",
                )
                if exc.status_code >= 500:
                    elasticapm_client.capture_exception(
                        context={"request": get_data_from_request(request, elasticapm_client.config, constants.ERROR)}
                    )
            raise
        except Exception:
            if elasticapm_client:
                elasticapm.set_transaction_result("HTTP 5xx", override=False)
                elasticapm.set_transaction_outcome(http_status_code=500, override=False)
                elasticapm.set_context({"status_code": 500}, "response")
                elasticapm_client.capture_exception(
                    context={"request": get_data_from_request(request, elasticapm_client.config, constants.ERROR)}
                )
            raise
        finally:
            elasticapm_client.end_transaction()

    # decorating with @middleware is only required in aiohttp < 4.0, and we only support 3+
    if aiohttp.__version__.startswith("3"):
        return middleware(handle_request)
    return handle_request
