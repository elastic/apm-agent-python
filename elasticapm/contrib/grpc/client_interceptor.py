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

from typing import Optional

import grpc
from grpc._interceptor import _ClientCallDetails

import elasticapm
from elasticapm.conf import constants
from elasticapm.traces import Span
from elasticapm.utils import default_ports


class _ClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    # grpc.UnaryStreamClientInterceptor,
    # grpc.StreamUnaryClientInterceptor,
    # grpc.StreamStreamClientInterceptor,
):
    def __init__(self, host: Optional[str], port: Optional[str], secure: bool):
        self.host: str = host
        self.port: str = port
        self.secure: bool = secure
        schema = "https" if secure else "http"
        resource = f"{schema}://{host}"
        if port and int(port) != default_ports[schema]:
            resource += f":{port}"

        self._context = {
            "http": {
                "url": resource,
            },
            "destination": {
                "address": host,
                "port": port,
            },
        }

    def intercept_unary_unary(self, continuation, client_call_details, request):
        """Intercepts a unary-unary invocation asynchronously.

        Args:
          continuation: A function that proceeds with the invocation by
            executing the next interceptor in chain or invoking the
            actual RPC on the underlying Channel. It is the interceptor's
            responsibility to call it if it decides to move the RPC forward.
            The interceptor can use
            `response_future = continuation(client_call_details, request)`
            to continue with the RPC. `continuation` returns an object that is
            both a Call for the RPC and a Future. In the event of RPC
            completion, the return Call-Future's result value will be
            the response message of the RPC. Should the event terminate
            with non-OK status, the returned Call-Future's exception value
            will be an RpcError.
          client_call_details: A ClientCallDetails object describing the
            outgoing RPC.
          request: The request value for the RPC.

        Returns:
            An object that is both a Call for the RPC and a Future.
            In the event of RPC completion, the return Call-Future's
            result value will be the response message of the RPC.
            Should the event terminate with non-OK status, the returned
            Call-Future's exception value will be an RpcError.
        """
        with elasticapm.capture_span(
            client_call_details.method, span_type="external", span_subtype="grpc", extra=self._context.copy(), leaf=True
        ) as span:
            client_call_details = self.attach_traceparent(client_call_details, span)
            try:
                response = continuation(client_call_details, request)
            except grpc.RpcError:
                span.set_failure()
                raise

            return response

    # TODO: instrument other types of requests once the spec is ready

    # def intercept_unary_stream(self, continuation, client_call_details,
    #                            request):
    #     """Intercepts a unary-stream invocation.
    #
    #     Args:
    #       continuation: A function that proceeds with the invocation by
    #         executing the next interceptor in chain or invoking the
    #         actual RPC on the underlying Channel. It is the interceptor's
    #         responsibility to call it if it decides to move the RPC forward.
    #         The interceptor can use
    #         `response_iterator = continuation(client_call_details, request)`
    #         to continue with the RPC. `continuation` returns an object that is
    #         both a Call for the RPC and an iterator for response values.
    #         Drawing response values from the returned Call-iterator may
    #         raise RpcError indicating termination of the RPC with non-OK
    #         status.
    #       client_call_details: A ClientCallDetails object describing the
    #         outgoing RPC.
    #       request: The request value for the RPC.
    #
    #     Returns:
    #         An object that is both a Call for the RPC and an iterator of
    #         response values. Drawing response values from the returned
    #         Call-iterator may raise RpcError indicating termination of
    #         the RPC with non-OK status. This object *should* also fulfill the
    #         Future interface, though it may not.
    #     """
    #     response_iterator = continuation(client_call_details, request)
    #     return response_iterator
    #
    # def intercept_stream_unary(self, continuation, client_call_details,
    #                            request_iterator):
    #     """Intercepts a stream-unary invocation asynchronously.
    #
    #     Args:
    #       continuation: A function that proceeds with the invocation by
    #         executing the next interceptor in chain or invoking the
    #         actual RPC on the underlying Channel. It is the interceptor's
    #         responsibility to call it if it decides to move the RPC forward.
    #         The interceptor can use
    #         `response_future = continuation(client_call_details, request_iterator)`
    #         to continue with the RPC. `continuation` returns an object that is
    #         both a Call for the RPC and a Future. In the event of RPC completion,
    #         the return Call-Future's result value will be the response message
    #         of the RPC. Should the event terminate with non-OK status, the
    #         returned Call-Future's exception value will be an RpcError.
    #       client_call_details: A ClientCallDetails object describing the
    #         outgoing RPC.
    #       request_iterator: An iterator that yields request values for the RPC.
    #
    #     Returns:
    #       An object that is both a Call for the RPC and a Future.
    #       In the event of RPC completion, the return Call-Future's
    #       result value will be the response message of the RPC.
    #       Should the event terminate with non-OK status, the returned
    #       Call-Future's exception value will be an RpcError.
    #     """
    #
    # def intercept_stream_stream(self, continuation, client_call_details,
    #                             request_iterator):
    #     """Intercepts a stream-stream invocation.
    #
    #     Args:
    #       continuation: A function that proceeds with the invocation by
    #         executing the next interceptor in chain or invoking the
    #         actual RPC on the underlying Channel. It is the interceptor's
    #         responsibility to call it if it decides to move the RPC forward.
    #         The interceptor can use
    #         `response_iterator = continuation(client_call_details, request_iterator)`
    #         to continue with the RPC. `continuation` returns an object that is
    #         both a Call for the RPC and an iterator for response values.
    #         Drawing response values from the returned Call-iterator may
    #         raise RpcError indicating termination of the RPC with non-OK
    #         status.
    #       client_call_details: A ClientCallDetails object describing the
    #         outgoing RPC.
    #       request_iterator: An iterator that yields request values for the RPC.
    #
    #     Returns:
    #       An object that is both a Call for the RPC and an iterator of
    #       response values. Drawing response values from the returned
    #       Call-iterator may raise RpcError indicating termination of
    #       the RPC with non-OK status. This object *should* also fulfill the
    #       Future interface, though it may not.
    #     """

    def attach_traceparent(self, client_call_details: _ClientCallDetails, span: Span):
        if not span.transaction:
            return client_call_details
        meta = list(client_call_details.metadata) if client_call_details.metadata else []
        if constants.TRACEPARENT_HEADER_NAME not in meta:
            traceparent = span.transaction.trace_parent.copy_from(span_id=span.id)
            meta.extend(
                (
                    (constants.TRACEPARENT_HEADER_NAME, traceparent.to_string()),
                    (constants.TRACESTATE_HEADER_NAME, traceparent.tracestate),
                )
            )
        return client_call_details._replace(metadata=meta)
