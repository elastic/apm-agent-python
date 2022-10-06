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
from elasticapm.instrumentation.packages.botocore import (
    BotocoreInstrumentation,
    post_span_modifiers,
    pre_span_modifiers,
)


class AioBotocoreInstrumentation(BotocoreInstrumentation):
    name = "aiobotocore"

    instrument_list = [("aiobotocore.client", "AioBaseClient._make_api_call")]

    capture_span_ctx = async_capture_span

    async def call(self, module, method, wrapped, instance, args, kwargs):
        service = self._get_service(instance)

        ctx = self._call(service, instance, args, kwargs)
        async with ctx as span:
            if service in pre_span_modifiers:
                pre_span_modifiers[service](span, args, kwargs)
            result = await wrapped(*args, **kwargs)
            if service in post_span_modifiers:
                post_span_modifiers[service](span, args, kwargs, result)
            request_id = result.get("ResponseMetadata", {}).get("RequestId")
            if request_id:
                span.update_context("http", {"request": {"id": request_id}})
            return result
