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

from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.utils import get_host_from_url, sanitize_url, url_to_destination


class HttpxAsyncClientInstrumentation(AsyncAbstractInstrumentedModule):
    name = "httpx"

    instrument_list = [("httpx", "AsyncClient.send")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        request = kwargs.get("request", args[0])

        request_method = request.method.upper()
        url = str(request.url)
        name = "{request_method} {host}".format(request_method=request_method, host=get_host_from_url(url))
        url = sanitize_url(url)
        destination = url_to_destination(url)

        async with async_capture_span(
            name,
            span_type="external",
            span_subtype="http",
            extra={"http": {"url": url}, "destination": destination},
            leaf=True,
        ) as span:
            response = await wrapped(*args, **kwargs)
            if response is not None:
                if span.context:
                    span.context["http"]["status_code"] = response.status_code
                span.set_success() if response.status_code < 400 else span.set_failure()
            return response
