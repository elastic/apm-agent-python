#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import inspect

import grpc

import elasticapm
from elasticapm.contrib.grpc.server_interceptor import _ServicerContextWrapper, get_trace_parent


class _AsyncServerInterceptor(grpc.aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        def wrap_unary_unary(behavior):
            async def _interceptor(request, context):
                tp = get_trace_parent(handler_call_details)
                client = elasticapm.get_client()
                transaction = client.begin_transaction("request", trace_parent=tp)
                try:
                    result = behavior(request, _ServicerContextWrapper(context, transaction))

                    # This is so we can support both sync and async rpc functions
                    if inspect.isawaitable(result):
                        result = await result

                    if transaction and not transaction.outcome:
                        transaction.set_success()
                    return result
                except Exception:
                    if transaction:
                        transaction.set_failure()
                    client.capture_exception(handled=False)
                    raise
                finally:
                    client.end_transaction(name=handler_call_details.method)

            return _interceptor

        handler = await continuation(handler_call_details)
        if handler.request_streaming or handler.response_streaming:
            return handler

        return grpc.unary_unary_rpc_method_handler(
            wrap_unary_unary(handler.unary_unary),
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
