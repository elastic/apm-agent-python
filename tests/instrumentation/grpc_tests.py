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

import pytest

grpc = pytest.importorskip("grpc")

from unittest.mock import MagicMock, patch, call

pytestmark = pytest.mark.grpc

from elasticapm.instrumentation.packages.grpc import (
    GRPCClientInstrumentation,
    GRPCServerInstrumentation,
    GRPCAsyncServerInstrumentation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_instrumentation():
    return GRPCClientInstrumentation()


def _make_server_instrumentation():
    return GRPCServerInstrumentation()


def _make_async_server_instrumentation():
    return GRPCAsyncServerInstrumentation()


# ---------------------------------------------------------------------------
# GRPCClientInstrumentation
# ---------------------------------------------------------------------------


class TestGRPCClientInstrumentation:
    def test_insecure_channel_positional_arg_parses_host_port(self):
        """insecure_channel called with 'host:port' as positional arg."""
        instrumentation = _make_client_instrumentation()
        fake_channel = MagicMock()
        wrapped = MagicMock(return_value=fake_channel)
        intercepted_channel = MagicMock()

        with patch("grpc.intercept_channel", return_value=intercepted_channel) as mock_intercept, \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor") as MockInterceptor:
            result = instrumentation.call(
                module="grpc",
                method="insecure_channel",
                wrapped=wrapped,
                instance=None,
                args=("myhost:50051",),
                kwargs={},
            )

        wrapped.assert_called_once_with("myhost:50051")
        MockInterceptor.assert_called_once_with("myhost", 50051, secure=False)
        mock_intercept.assert_called_once_with(fake_channel, MockInterceptor.return_value)
        assert result is intercepted_channel

    def test_insecure_channel_keyword_arg_parses_host_port(self):
        """insecure_channel called with target= kwarg."""
        instrumentation = _make_client_instrumentation()
        fake_channel = MagicMock()
        wrapped = MagicMock(return_value=fake_channel)

        with patch("grpc.intercept_channel") as mock_intercept, \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="insecure_channel",
                wrapped=wrapped,
                instance=None,
                args=(),
                kwargs={"target": "myhost:8080"},
            )

        MockInterceptor.assert_called_once_with("myhost", 8080, secure=False)

    def test_secure_channel_sets_secure_flag(self):
        """secure_channel passes secure=True to _ClientInterceptor."""
        instrumentation = _make_client_instrumentation()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("grpc.intercept_channel"), \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="secure_channel",
                wrapped=wrapped,
                instance=None,
                args=("myhost:443",),
                kwargs={},
            )

        MockInterceptor.assert_called_once_with("myhost", 443, secure=True)

    def test_host_without_port(self):
        """Target with no colon produces port=None."""
        instrumentation = _make_client_instrumentation()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("grpc.intercept_channel"), \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="insecure_channel",
                wrapped=wrapped,
                instance=None,
                args=("myhost",),
                kwargs={},
            )

        MockInterceptor.assert_called_once_with("myhost", None, secure=False)

    def test_non_integer_port_becomes_none(self):
        """If port segment is not a valid integer, port is set to None."""
        instrumentation = _make_client_instrumentation()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("grpc.intercept_channel"), \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="insecure_channel",
                wrapped=wrapped,
                instance=None,
                args=("myhost:notaport",),
                kwargs={},
            )

        MockInterceptor.assert_called_once_with("myhost", None, secure=False)

    def test_returns_intercepted_channel(self):
        """The return value is whatever grpc.intercept_channel returns."""
        instrumentation = _make_client_instrumentation()
        sentinel = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("grpc.intercept_channel", return_value=sentinel), \
             patch("elasticapm.contrib.grpc.client_interceptor._ClientInterceptor"):
            result = instrumentation.call(
                module="grpc",
                method="insecure_channel",
                wrapped=wrapped,
                instance=None,
                args=("host:1234",),
                kwargs={},
            )

        assert result is sentinel


# ---------------------------------------------------------------------------
# GRPCServerInstrumentation
# ---------------------------------------------------------------------------


class TestGRPCServerInstrumentation:
    def test_no_interceptors_adds_server_interceptor_via_kwargs(self):
        """With no existing interceptors, _ServerInterceptor is added via kwargs."""
        instrumentation = _make_server_instrumentation()
        fake_server = MagicMock()
        wrapped = MagicMock(return_value=fake_server)

        with patch("elasticapm.contrib.grpc.server_interceptor._ServerInterceptor") as MockInterceptor:
            result = instrumentation.call(
                module="grpc",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(),
                kwargs={},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert result is fake_server

    def test_existing_interceptors_via_kwargs_prepends_server_interceptor(self):
        """_ServerInterceptor is inserted at index 0, before existing interceptors."""
        instrumentation = _make_server_instrumentation()
        existing = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("elasticapm.contrib.grpc.server_interceptor._ServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(),
                kwargs={"interceptors": [existing]},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert interceptors_passed[1] is existing

    def test_existing_interceptors_via_positional_args(self):
        """_ServerInterceptor is prepended when interceptors are in args[2]."""
        instrumentation = _make_server_instrumentation()
        existing = MagicMock()
        thread_pool = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        # args[0]=thread_pool, args[1]=options, args[2]=interceptors
        with patch("elasticapm.contrib.grpc.server_interceptor._ServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(thread_pool, None, [existing]),
                kwargs={},
            )

        call_args = wrapped.call_args.args
        interceptors_passed = call_args[2]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert interceptors_passed[1] is existing

    def test_no_interceptors_in_positional_args_uses_kwargs(self):
        """When args has fewer than 3 elements, interceptors go to kwargs."""
        instrumentation = _make_server_instrumentation()
        thread_pool = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("elasticapm.contrib.grpc.server_interceptor._ServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(thread_pool,),
                kwargs={},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value


# ---------------------------------------------------------------------------
# GRPCAsyncServerInstrumentation
# ---------------------------------------------------------------------------


class TestGRPCAsyncServerInstrumentation:
    def test_no_interceptors_adds_async_interceptor_via_kwargs(self):
        """With no existing interceptors, _AsyncServerInterceptor is added via kwargs."""
        instrumentation = _make_async_server_instrumentation()
        fake_server = MagicMock()
        wrapped = MagicMock(return_value=fake_server)

        with patch("elasticapm.contrib.grpc.async_server_interceptor._AsyncServerInterceptor") as MockInterceptor:
            result = instrumentation.call(
                module="grpc.aio",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(),
                kwargs={},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert result is fake_server

    def test_existing_interceptors_via_kwargs_prepends_async_interceptor(self):
        """_AsyncServerInterceptor is inserted at index 0 before existing interceptors."""
        instrumentation = _make_async_server_instrumentation()
        existing = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("elasticapm.contrib.grpc.async_server_interceptor._AsyncServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc.aio",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(),
                kwargs={"interceptors": [existing]},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert interceptors_passed[1] is existing

    def test_existing_interceptors_via_positional_args(self):
        """_AsyncServerInterceptor is prepended when interceptors are in args[2]."""
        instrumentation = _make_async_server_instrumentation()
        existing = MagicMock()
        thread_pool = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("elasticapm.contrib.grpc.async_server_interceptor._AsyncServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc.aio",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(thread_pool, None, [existing]),
                kwargs={},
            )

        call_args = wrapped.call_args.args
        interceptors_passed = call_args[2]
        assert interceptors_passed[0] is MockInterceptor.return_value
        assert interceptors_passed[1] is existing

    def test_no_interceptors_in_short_positional_args_uses_kwargs(self):
        """When args has fewer than 3 elements, interceptors go to kwargs."""
        instrumentation = _make_async_server_instrumentation()
        thread_pool = MagicMock()
        wrapped = MagicMock(return_value=MagicMock())

        with patch("elasticapm.contrib.grpc.async_server_interceptor._AsyncServerInterceptor") as MockInterceptor:
            instrumentation.call(
                module="grpc.aio",
                method="server",
                wrapped=wrapped,
                instance=None,
                args=(thread_pool,),
                kwargs={},
            )

        interceptors_passed = wrapped.call_args.kwargs["interceptors"]
        assert interceptors_passed[0] is MockInterceptor.return_value
