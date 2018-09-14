import random
import string
import time

import mock

from elasticapm.transport.base import AsyncTransport, Transport, TransportException, TransportState
from elasticapm.utils import compat


def test_transport_state_should_try_online():
    state = TransportState()
    assert state.should_try() is True


def test_transport_state_should_try_new_error():
    state = TransportState()
    state.status = state.ERROR
    state.last_check = time.time()
    state.retry_number = 1
    assert state.should_try() is False


def test_transport_state_should_try_time_passed_error():
    state = TransportState()
    state.status = state.ERROR
    state.last_check = time.time() - 10
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
    transport.flush()
    assert mock_send.call_count == 0


@mock.patch("elasticapm.transport.base.Transport.send")
def test_metadata_prepended(mock_send):
    transport = Transport(metadata={"x": "y"}, max_flush_time=5, compress_level=0)
    transport.queue("error", {}, flush=True)
    assert mock_send.call_count == 1
    args, kwargs = mock_send.call_args
    data = args[0]
    if compat.PY3:
        data = data.tobytes()
    data = data.decode("utf-8").split("\n")
    assert "metadata" in data[0]


@mock.patch("elasticapm.transport.base.Transport.send")
def test_flush_time(mock_send, caplog):
    transport = Transport(metadata={}, max_flush_time=5)
    transport._last_flush = time.time() - 5.1
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport.queue("error", {})
    record = caplog.records[0]
    assert "5.1" in record.message
    assert mock_send.call_count == 1
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport.send")
def test_flush_time_size(mock_send, caplog):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(metadata={}, max_buffer_size=100)
        # we need to add lots of uncompressible data to fill up the gzip-internal buffer
        for i in range(9):
            transport.queue("error", "".join(random.choice(string.ascii_letters) for i in range(2000)))
    record = caplog.records[0]
    assert "queue size" in record.message
    assert mock_send.call_count == 1
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport.send")
def test_forced_flush(mock_send, caplog):
    with caplog.at_level("DEBUG", "elasticapm.transport"):
        transport = Transport(metadata={}, max_buffer_size=1000, compress_level=0)
        transport.queue("error", "x", flush=True)
    record = caplog.records[0]
    assert "forced" in record.message
    assert mock_send.call_count == 1
    assert transport._queued_data is None


@mock.patch("elasticapm.transport.base.Transport.send")
def test_sync_transport_fail_and_recover(mock_send, caplog):
    mock_send.side_effect = TransportException("meh")
    transport = Transport()
    transport.queue("x", {}, flush=True)
    assert transport.state.did_fail()
    # first retry should be allowed immediately
    assert transport.state.should_try()

    # recover
    mock_send.side_effect = None
    transport.queue("x", {}, flush=True)
    assert not transport.state.did_fail()


@mock.patch("elasticapm.transport.base.Transport.send")
def test_sync_transport_fail_and_recover(mock_send, caplog):
    mock_send.side_effect = TransportException("meh")
    transport = AsyncTransport()
    transport.queue("x", {}, flush=True)
    transport.worker._timed_queue_join(1)
    assert transport.state.did_fail()
    # first retry should be allowed immediately
    assert transport.state.should_try()

    # recover
    mock_send.side_effect = None
    transport.queue("x", {}, flush=True)
    transport.worker._timed_queue_join(1)
    assert not transport.state.did_fail()

    transport.close()
