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

import logging
import sys
from concurrent import futures

import grpc

import elasticapm
from elasticapm.contrib.grpc import GRPCApmClient

from . import testgrpc_pb2 as pb2
from . import testgrpc_pb2_grpc as pb2_grpc

elasticapm.instrument()


class TestService(pb2_grpc.TestServiceServicer):
    def __init__(self, *args, **kwargs):
        pass

    def GetServerResponse(self, request, context):
        message = request.message
        result = f'Hello I am up and running received "{message}" message from you'
        result = {"message": result, "received": True}

        return pb2.MessageResponse(**result)

    def GetServerResponseAbort(self, request, context):
        context.abort(grpc.StatusCode.INTERNAL, "foo")

    def GetServerResponseUnavailable(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNAVAILABLE)
        context.set_details("Method not available")
        return pb2.MessageResponse(message="foo", received=True)

    def GetServerResponseException(self, request, context):
        raise Exception("oh no")


def serve(port):
    apm_client = GRPCApmClient(
        service_name="grpc-server", disable_metrics="*", api_request_time="100ms", central_config="False"
    )
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    pb2_grpc.add_TestServiceServicer_to_server(TestService(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = "50051"
    logging.basicConfig()
    serve(port)
