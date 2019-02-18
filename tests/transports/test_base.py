import gzip
import random
import string
import time
import timeit

import mock
import pytest

from elasticapm.transport.base import AsyncTransport, Transport, TransportException, TransportState
from elasticapm.utils import compat


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
        transport._flush()
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
    transport = Transport(metadata={}, max_flush_time=5, start_event_processor=False)
    transport._last_flush = timeit.default_timer() - 5.1
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport.queue("error", {})
        transport.close()
    record = caplog.records[0]
    assert "5.1" in record.message
    assert mock_send.call_count == 2  # one for the send, one for the close
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport._flush")
def test_flush_time_size(mock_flush, caplog):
    transport = Transport(metadata={}, max_buffer_size=100)
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        # we need to add lots of uncompressible data to fill up the gzip-internal buffer
        for i in range(9):
            transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
    transport.close()
    assert mock_flush.call_count == 2


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
        transport.queue("x", {}, flush=True)
        assert transport.state.did_fail()
        # first retry should be allowed immediately
        assert transport.state.should_try()

        # recover
        mock_send.side_effect = None
        transport.queue("x", {}, flush=True)
        assert not transport.state.did_fail()
    finally:
        transport.close()


@mock.patch("elasticapm.transport.base.Transport.send")
def test_sync_transport_fail_and_recover(mock_send, caplog):
    transport = AsyncTransport()

    try:
        mock_send.side_effect = TransportException("meh")
        transport.queue("x", {}, flush=True)
        time.sleep(0.1)
        transport.worker._timed_queue_join(1)
        assert transport.state.did_fail()
        # first retry should be allowed immediately
        assert transport.state.should_try()

        # recover
        mock_send.side_effect = None
        transport.queue("x", {}, flush=True)
        time.sleep(0.1)
        transport.worker._timed_queue_join(1)
        assert not transport.state.did_fail()
    finally:
        transport.close()


@pytest.mark.parametrize("sending_elasticapm_client", [{"api_request_time": "2s"}], indirect=True)
def test_send_timer(sending_elasticapm_client, caplog):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        assert sending_elasticapm_client.config.api_request_time == 2000
        sending_elasticapm_client.begin_transaction("test_type")
        sending_elasticapm_client.end_transaction("test")

        sending_elasticapm_client.close()

    assert "Sent request" in caplog.records[0].message


def test_compress_level_sanitization():
    assert Transport(compress_level=None)._compress_level == 0
    assert Transport(compress_level=-1)._compress_level == 0
    assert Transport(compress_level=10)._compress_level == 9
