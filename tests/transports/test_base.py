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

import gzip
import random
import string
import time
import timeit

import mock
import pytest

from elasticapm.transport.base import Transport, TransportState
from elasticapm.transport.exceptions import TransportException
from tests.fixtures import DummyTransport, TempStoreClient
from tests.utils import assert_any_record_contains


def test_transport_state_should_try_online():
    state = TransportState()
    assert state.should_try() is True


def test_transport_state_should_try_new_error():
    state = TransportState()
    state.status = state.ERROR
    state.last_check = timeit.default_timer()
    state.retry_number = 1
    assert state.should_try() is False


def test_transport_state_should_try_time_passed_error():
    state = TransportState()
    state.status = state.ERROR
    state.last_check = timeit.default_timer() - 10
    state.retry_number = 1
    assert state.should_try() is True


def test_transport_state_set_fail():
    state = TransportState()
    state.set_fail()
    assert state.status == state.ERROR
    assert state.last_check is not None
    assert state.retry_number == 0


def test_transport_state_set_success():
    state = TransportState()
    state.status = state.ERROR
    state.last_check = "foo"
    state.retry_number = 5
    state.set_success()
    assert state.status == state.ONLINE
    assert state.last_check is None
    assert state.retry_number == -1


@mock.patch("elasticapm.transport.base.Transport.send")
@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"api_request_time": "5s", "server_url": "http://localhost:8200"},
        {"api_request_time": "5s", "server_url": "http://remotehost:8200"},
    ],
    indirect=True,
)
def test_empty_queue_flush(mock_send, elasticapm_client):
    transport = Transport(client=elasticapm_client)
    try:
        transport.start_thread()
        transport.flush()
        if "localhost:" in elasticapm_client.config.server_url:
            assert mock_send.call_count == 1
        else:
            assert mock_send.call_count == 0
    finally:
        transport.close()


@mock.patch("elasticapm.transport.base.Transport.send")
@pytest.mark.parametrize("elasticapm_client", [{"api_request_time": "5s"}], indirect=True)
def test_metadata_prepended(mock_send, elasticapm_client):
    transport = Transport(client=elasticapm_client, compress_level=0)
    transport.start_thread()
    transport.queue("error", {}, flush=True)
    transport.close()
    assert mock_send.call_count == 1
    args, kwargs = mock_send.call_args
    data = gzip.decompress(args[0])
    data = data.decode("utf-8").split("\n")
    assert "metadata" in data[0]


@mock.patch("elasticapm.transport.base.Transport.send")
@pytest.mark.parametrize("elasticapm_client", [{"api_request_time": "100ms"}], indirect=True)
def test_flush_time(mock_send, caplog, elasticapm_client):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(client=elasticapm_client)
        transport.start_thread()
        # let first run finish
        time.sleep(0.2)
        transport.close()
    assert_any_record_contains(caplog.records, "due to time since last flush", "elasticapm.transport")
    assert mock_send.call_count == 0


@pytest.mark.flaky(reruns=3)  # test is flaky on Windows
@mock.patch("elasticapm.transport.base.Transport.send")
def test_api_request_time_dynamic(mock_send, caplog, elasticapm_client):
    elasticapm_client.config.update(version="1", api_request_time="1s")
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(client=elasticapm_client)
        transport.start_thread()
        # let first run finish
        time.sleep(0.2)
        transport.close()
    assert not caplog.records
    assert mock_send.call_count == 0
    elasticapm_client.config.update(version="1", api_request_time="100ms")
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(client=elasticapm_client)
        transport.start_thread()
        # let first run finish
        time.sleep(0.2)
        transport.close()
    assert_any_record_contains(caplog.records, "due to time since last flush", "elasticapm.transport")
    assert mock_send.call_count == 0


@mock.patch("elasticapm.transport.base.Transport._flush")
def test_api_request_size_dynamic(mock_flush, caplog, elasticapm_client):
    elasticapm_client.config.update(version="1", api_request_size="100b")
    transport = Transport(client=elasticapm_client, queue_chill_count=1)
    transport.start_thread()
    try:
        with caplog.at_level("DEBUG", "elasticapm.transport"):
            # we need to add lots of uncompressible data to fill up the gzip-internal buffer
            for i in range(12):
                transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
            transport._flushed.wait(timeout=0.1)
        assert mock_flush.call_count == 1
        elasticapm_client.config.update(version="1", api_request_size="1mb")
        with caplog.at_level("DEBUG", "elasticapm.transport"):
            # we need to add lots of uncompressible data to fill up the gzip-internal buffer
            for i in range(12):
                transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
            transport._flushed.wait(timeout=0.1)
        # Should be unchanged because our buffer limit is much higher.
        assert mock_flush.call_count == 1
    finally:
        transport.close()


@mock.patch("elasticapm.transport.base.Transport._flush")
@pytest.mark.parametrize("elasticapm_client", [{"api_request_size": "100b"}], indirect=True)
def test_flush_time_size(mock_flush, caplog, elasticapm_client):
    transport = Transport(client=elasticapm_client, queue_chill_count=1)
    transport.start_thread()
    try:
        with caplog.at_level("DEBUG", "elasticapm.transport"):
            # we need to add lots of uncompressible data to fill up the gzip-internal buffer
            for i in range(12):
                transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
            transport._flushed.wait(timeout=0.1)
        assert mock_flush.call_count == 1
    finally:
        transport.close()


@mock.patch("elasticapm.transport.base.Transport.send")
@pytest.mark.parametrize("elasticapm_client", [{"api_request_size": "1000b"}], indirect=True)
def test_forced_flush(mock_send, caplog, elasticapm_client):
    transport = Transport(client=elasticapm_client, compress_level=0)
    transport.start_thread()
    try:
        with caplog.at_level("DEBUG", "elasticapm.transport"):
            transport.queue("error", "x", flush=True)
    finally:
        transport.close()
    assert mock_send.call_count == 1
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport.send")
def test_sync_transport_fail_and_recover(mock_send, caplog):
    transport = Transport(client=None)
    transport.start_thread()
    try:
        mock_send.side_effect = TransportException("meh")
        transport.queue("x", {})
        transport.flush()
        assert transport.state.did_fail()
        # first retry should be allowed immediately
        assert transport.state.should_try()

        # recover
        mock_send.side_effect = None
        transport.queue("x", {})
        transport.flush()
        assert not transport.state.did_fail()
    finally:
        transport.close()


@pytest.mark.parametrize("sending_elasticapm_client", [{"api_request_time": "2s"}], indirect=True)
def test_send_timer(sending_elasticapm_client, caplog):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        assert sending_elasticapm_client.config.api_request_time.total_seconds() == 2
        sending_elasticapm_client.begin_transaction("test_type")
        sending_elasticapm_client.end_transaction("test")

        sending_elasticapm_client._transport.flush()

    assert_any_record_contains(caplog.records, "Sent request")


def test_compress_level_sanitization():
    assert DummyTransport(compress_level=None, url="", client=None)._compress_level == 0
    assert DummyTransport(compress_level=-1, url="", client=None)._compress_level == 0
    assert DummyTransport(compress_level=10, url="", client=None)._compress_level == 9


@mock.patch("elasticapm.transport.base.Transport.send")
def test_transport_metadata_pid_change(mock_send, elasticapm_client):
    transport = Transport(client=elasticapm_client)
    assert not transport._metadata
    transport.start_thread()
    time.sleep(0.2)
    assert transport._metadata
    transport.close()


def test_flushed_arg(sending_elasticapm_client):
    sending_elasticapm_client.begin_transaction("test_type")
    sending_elasticapm_client.end_transaction("test")
    sending_elasticapm_client._transport.flush()

    assert sending_elasticapm_client.httpserver.requests[0].args["flushed"] == "true"


@pytest.mark.flaky(reruns=3)  # Trying to test automatic flushes is inherently flaky
@pytest.mark.parametrize("sending_elasticapm_client", [{"api_request_time": "100ms"}], indirect=True)
def test_flushed_arg_with_wait(sending_elasticapm_client):
    sending_elasticapm_client.begin_transaction("test_type")
    sending_elasticapm_client.end_transaction("test")
    time.sleep(0.3)
    sending_elasticapm_client._transport.flush()

    assert sending_elasticapm_client.httpserver.requests[1].args["flushed"] == "true"
