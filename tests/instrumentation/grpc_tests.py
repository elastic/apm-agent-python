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

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span

pytestmark = pytest.mark.grpc


def test_grpc_client_instrumentation(instrument, elasticapm_client):
    """Test that gRPC client instrumentation creates transactions and adds interceptors"""
    # Create a test channel
    channel = grpc.insecure_channel("localhost:50051")
    
    # Verify that the channel was created with our interceptor
    assert hasattr(channel, "_interceptor")
    assert channel._interceptor.__class__.__name__ == "_ClientInterceptor"
    
    # Verify transaction was created
    transaction = elasticapm_client.events[TRANSACTION][0]
    assert transaction["type"] == "script"
    assert transaction["name"] == "grpc_client_instrumentation"


def test_grpc_secure_channel_instrumentation(instrument, elasticapm_client):
    """Test that secure channel instrumentation works correctly"""
    # Create a secure channel
    channel = grpc.secure_channel("localhost:50051", grpc.local_channel_credentials())
    
    # Verify that the channel was created with our interceptor
    assert hasattr(channel, "_interceptor")
    assert channel._interceptor.__class__.__name__ == "_ClientInterceptor"
    
    # Verify transaction was created
    transaction = elasticapm_client.events[TRANSACTION][0]
    assert transaction["type"] == "script"
    assert transaction["name"] == "grpc_client_instrumentation"


def test_grpc_server_instrumentation(instrument, elasticapm_client):
    """Test that gRPC server instrumentation adds interceptors"""
    # Create a test server
    server = grpc.server(None)
    
    # Verify that the server was created with our interceptor
    assert len(server._interceptors) > 0
    assert server._interceptors[0].__class__.__name__ == "_ServerInterceptor"
    
    # Verify transaction was created
    transaction = elasticapm_client.events[TRANSACTION][0]
    assert transaction["type"] == "script"
    assert transaction["name"] == "grpc_server_instrumentation"


def test_grpc_async_server_instrumentation(instrument, elasticapm_client):
    """Test that async server instrumentation adds interceptors"""
    # Create a test async server
    server = grpc.aio.server()
    
    # Verify that the server was created with our interceptor
    assert len(server._interceptors) > 0
    assert server._interceptors[0].__class__.__name__ == "_AsyncServerInterceptor"
    
    # Verify transaction was created
    transaction = elasticapm_client.events[TRANSACTION][0]
    assert transaction["type"] == "script"
    assert transaction["name"] == "grpc_async_server_instrumentation"


def test_grpc_client_target_parsing(instrument, elasticapm_client):
    """Test that target parsing works correctly for different formats"""
    # Test with host:port format
    channel = grpc.insecure_channel("localhost:50051")
    assert channel._interceptor.host == "localhost"
    assert channel._interceptor.port == 50051
    
    # Test with just host format
    channel = grpc.insecure_channel("localhost")
    assert channel._interceptor.host == "localhost"
    assert channel._interceptor.port is None
    
    # Test with invalid port format
    channel = grpc.insecure_channel("localhost:invalid")
    assert channel._interceptor.host == "localhost"
    assert channel._interceptor.port is None 