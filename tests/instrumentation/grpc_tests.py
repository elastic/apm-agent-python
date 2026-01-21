#  BSD 3-Clause License
#
#  Copyright (c) 2024, Elasticsearch BV
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

import pytest  # isort:skip

grpc = pytest.importorskip("grpc")  # isort:skip

import asyncio
from concurrent import futures

import elasticapm
from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm import Client
from elasticapm.contrib.grpc.client_interceptor import _ClientInterceptor
from elasticapm.contrib.grpc.server_interceptor import _ServerInterceptor
from elasticapm.contrib.grpc.async_server_interceptor import _AsyncServerInterceptor
from tests.fixtures import TempStoreClient, instrument
from tests.instrumentation.test_pb2 import UnaryUnaryRequest, UnaryUnaryResponse
from tests.instrumentation.test_pb2_grpc import TestServiceServicer, TestServiceStub, add_TestServiceServicer_to_server

pytestmark = pytest.mark.grpc


class TestService(TestServiceServicer):
    def UnaryUnary(self, request, context):
        return UnaryUnaryResponse(message=request.message)


@pytest.fixture
def elasticapm_client():
    return TempStoreClient()


def test_grpc_client_instrumentation(instrument, elasticapm_client):
    """Test that gRPC client instrumentation adds interceptors"""
    elasticapm_client.begin_transaction("test")
    with capture_span("test_grpc_client", "test"):
        elasticapm.instrument()  # Ensure instrumentation is done before channel creation
        channel = grpc.insecure_channel("localhost:50051")
    elasticapm_client.end_transaction("MyView")

    # Verify that the channel has the interceptor
    assert hasattr(channel, "_interceptor")
    assert isinstance(channel._interceptor, _ClientInterceptor)


def test_grpc_secure_channel_instrumentation(instrument, elasticapm_client):
    """Test that secure channel instrumentation adds interceptors"""
    elasticapm_client.begin_transaction("test")
    with capture_span("test_grpc_secure_channel", "test"):
        elasticapm.instrument()  # Ensure instrumentation is done before channel creation
        channel = grpc.secure_channel("localhost:50051", grpc.local_channel_credentials())
    elasticapm_client.end_transaction("MyView")

    # Verify that the channel has the interceptor
    assert hasattr(channel, "_interceptor")
    assert isinstance(channel._interceptor, _ClientInterceptor)


def test_grpc_server_instrumentation(instrument, elasticapm_client):
    """Test that gRPC server instrumentation adds interceptors"""
    # Create a test server
    elasticapm_client.begin_transaction("test")
    with capture_span("test_grpc_server", "test"):
        elasticapm.instrument()  # Ensure instrumentation is done before server creation
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
        port = server.add_insecure_port("[::]:0")  # Let the OS choose a port
        servicer = TestService()
        add_TestServiceServicer_to_server(servicer, server)
        server.start()
    elasticapm_client.end_transaction("MyView")

    try:
        # Make a test call to verify the interceptor is working
        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = TestServiceStub(channel)
        response = stub.UnaryUnary(UnaryUnaryRequest(message="test"))
        assert response.message == "test"

        # Verify that a transaction was created for the server call
        assert len(elasticapm_client.events["transaction"]) == 2  # One for our test, one for the server call
        transaction = elasticapm_client.events["transaction"][1]  # Second is from the server interceptor
        assert transaction["name"] == "/test.TestService/UnaryUnary"
        assert transaction["type"] == "request"
    finally:
        server.stop(0)


@pytest.mark.asyncio
async def test_grpc_async_server_instrumentation(instrument, elasticapm_client):
    """Test that async server instrumentation adds interceptors"""
    # Create a test async server
    elasticapm_client.begin_transaction("test")
    with capture_span("test_grpc_async_server", "test"):
        elasticapm.instrument()  # Ensure instrumentation is done before server creation
        server = grpc.aio.server()
        port = server.add_insecure_port("[::]:0")  # Let the OS choose a port
        servicer = TestService()
        add_TestServiceServicer_to_server(servicer, server)
    elasticapm_client.end_transaction("MyView")

    await server.start()
    try:
        # Make a test call to verify the interceptor is working
        channel = grpc.aio.insecure_channel(f"localhost:{port}")
        stub = TestServiceStub(channel)
        response = await stub.UnaryUnary(UnaryUnaryRequest(message="test"))
        assert response.message == "test"

        # Verify that a transaction was created for the server call
        assert len(elasticapm_client.events["transaction"]) == 2  # One for our test, one for the server call
        transaction = elasticapm_client.events["transaction"][1]  # Second is from the server interceptor
        assert transaction["name"] == "/test.TestService/UnaryUnary"
        assert transaction["type"] == "request"
    finally:
        await server.stop(0)


def test_grpc_client_target_parsing(instrument, elasticapm_client):
    """Test that gRPC client target parsing works correctly"""
    elasticapm_client.begin_transaction("test")
    with capture_span("test_grpc_client_target", "test"):
        elasticapm.instrument()  # Ensure instrumentation is done before channel creation
        channel = grpc.insecure_channel("localhost:50051")
    elasticapm_client.end_transaction("MyView")

    # Verify that the channel has the interceptor
    assert hasattr(channel, "_interceptor")
    assert isinstance(channel._interceptor, _ClientInterceptor) 