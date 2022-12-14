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

import grpc
import wrapt

import elasticapm
from elasticapm.conf.constants import OUTCOME
from elasticapm.contrib.grpc.utils import STATUS_TO_OUTCOME
from elasticapm.utils.disttracing import TraceParent


# from https://github.com/grpc/grpc/issues/18191
def _wrap_rpc_behavior(handler, continuation):
    if handler is None:
        return None

    if handler.request_streaming and handler.response_streaming:
        behavior_fn = handler.stream_stream
        handler_factory = grpc.stream_stream_rpc_method_handler
    elif handler.request_streaming and not handler.response_streaming:
        behavior_fn = handler.stream_unary
        handler_factory = grpc.stream_unary_rpc_method_handler
    elif not handler.request_streaming and handler.response_streaming:
        behavior_fn = handler.unary_stream
        handler_factory = grpc.unary_stream_rpc_method_handler
    else:
        behavior_fn = handler.unary_unary
        handler_factory = grpc.unary_unary_rpc_method_handler

    return handler_factory(
        continuation(behavior_fn, handler.request_streaming, handler.response_streaming),
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )


class _ServicerContextWrapper(wrapt.ObjectProxy):
    def __init__(self, wrapped, transaction):
        self._self_transaction = transaction
        super().__init__(wrapped)

    def abort(self, code, details):
        transaction = self._self_transaction
        if transaction:
            transaction.set_failure()
        return self.__wrapped__.abort(code, details)

    def set_code(self, code):
        transaction = self._self_transaction
        if transaction:
            outcome = STATUS_TO_OUTCOME.get(code, OUTCOME.SUCCESS)
            transaction.set_success() if outcome is OUTCOME.SUCCESS else transaction.set_failure()
        return self.__wrapped__.set_code(code)


class _ServerInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        def transaction_wrapper(behavior, request_streaming, response_streaming):
            def _interceptor(request_or_iterator, context):
                if request_streaming or response_streaming:  # only unary-unary is supported
                    return behavior(request_or_iterator, context)
                traceparent, tracestate = None, None
                for metadata in handler_call_details.invocation_metadata:
                    if metadata.key == "traceparent":
                        traceparent = metadata.value
                    elif metadata.key == "tracestate":
                        tracestate = metadata.key
                if traceparent:
                    tp = TraceParent.from_string(traceparent, tracestate)
                else:
                    tp = None
                client = elasticapm.get_client()
                transaction = client.begin_transaction("request", trace_parent=tp)
                try:
                    result = behavior(request_or_iterator, _ServicerContextWrapper(context, transaction))
                    if not transaction.outcome:
                        transaction.set_success()
                    return result
                except Exception:
                    transaction.set_failure()
                    client.capture_exception(handled=False)
                    raise
                finally:
                    client.end_transaction(name=handler_call_details.method)

            return _interceptor

        return _wrap_rpc_behavior(continuation(handler_call_details), transaction_wrapper)
