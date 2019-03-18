import gzip
import random
import string
import time
import timeit

import mock
import pytest

from elasticapm.transport.base import AsyncTransport, Transport, TransportException, TransportState
from elasticapm.utils import compat
from tests.fixtures import DummyTransport, TempStoreClient


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
def test_empty_queue_flush_is_not_sent(mock_send):
    transport = Transport(metadata={"x": "y"}, max_flush_time=5)
    try:
        transport.flush()
        assert mock_send.call_count == 0
    finally:
        transport.close()


@mock.patch("elasticapm.transport.base.Transport.send")
def test_metadata_prepended(mock_send):
    transport = Transport(metadata={"x": "y"}, max_flush_time=5, compress_level=0)
    transport.queue("error", {}, flush=True)
    transport.close()
    assert mock_send.call_count == 1
    args, kwargs = mock_send.call_args
    if compat.PY2:
        data = gzip.GzipFile(fileobj=compat.StringIO(args[0])).read()
    else:
        data = gzip.decompress(args[0])
    data = data.decode("utf-8").split("\n")
    assert "metadata" in data[0]


@mock.patch("elasticapm.transport.base.Transport.send")
def test_flush_time(mock_send, caplog):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(metadata={}, max_flush_time=0.1)
        # let first run finish
        time.sleep(0.2)
        transport.close()
    record = caplog.records[0]
    assert "due to time since last flush" in record.message
    assert mock_send.call_count == 0


@mock.patch("elasticapm.transport.base.Transport._flush")
def test_flush_time_size(mock_flush, caplog):
    transport = Transport(metadata={}, max_buffer_size=100, queue_chill_count=1)
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        # we need to add lots of uncompressible data to fill up the gzip-internal buffer
        for i in range(12):
            transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
        transport._flushed.wait(timeout=0.1)
    assert mock_flush.call_count == 1
    transport.close()


@mock.patch("elasticapm.transport.base.Transport.send")
def test_forced_flush(mock_send, caplog):
    transport = Transport(metadata={}, max_buffer_size=1000, compress_level=0)
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport.queue("error", "x", flush=True)
    transport.close()
    assert mock_send.call_count == 1
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport.send")
def test_sync_transport_fail_and_recover(mock_send, caplog):
    transport = Transport()
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
        assert sending_elasticapm_client.config.api_request_time == 2000
        sending_elasticapm_client.begin_transaction("test_type")
        sending_elasticapm_client.end_transaction("test")

        sending_elasticapm_client._transport.flush()

    assert "Sent request" in caplog.records[1].message


@mock.patch("tests.fixtures.DummyTransport._start_event_processor")
@mock.patch("elasticapm.transport.base.is_master_process")
def test_client_doesnt_start_processor_thread_in_master_process(is_master_process, mock_start_event_processor):
    # when in the master process, the client should not start worker threads
    is_master_process.return_value = True
    before = mock_start_event_processor.call_count
    client = TempStoreClient(server_url="http://example.com", service_name="app_name", secret_token="secret")
    assert mock_start_event_processor.call_count == before
    client.close()

    is_master_process.return_value = False
    before = mock_start_event_processor.call_count
    client = TempStoreClient(server_url="http://example.com", service_name="app_name", secret_token="secret")
    assert mock_start_event_processor.call_count == before + 1
    client.close()


def test_compress_level_sanitization():
    assert DummyTransport(compress_level=None, url="")._compress_level == 0
    assert DummyTransport(compress_level=-1, url="")._compress_level == 0
    assert DummyTransport(compress_level=10, url="")._compress_level == 9
