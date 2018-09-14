import asyncio
import sys

import asynctest
import pytest
from pytest_localserver.http import ContentServer

from elasticapm.transport.base import TransportException

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5), reason="python3.5+ requried for asyncio")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sending_elasticapm_client",
    [{"transport_class": "elasticapm.transport.asyncio.AsyncioHTTPTransport"}],
    indirect=True,
)
async def test_client_success(sending_elasticapm_client):
    sending_elasticapm_client.capture_message("foo", handled=False)
    tasks = asyncio.Task.all_tasks()
    task = next(t for t in tasks if t is not asyncio.Task.current_task())
    await task
    assert not sending_elasticapm_client._transport.state.did_fail()
    error = sending_elasticapm_client.httpserver.payloads[0][1]["error"]
    assert error["log"]["message"] == "foo"
    await sending_elasticapm_client._transport.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sending_elasticapm_client",
    [{"transport_class": "elasticapm.transport.asyncio.AsyncioHTTPTransport"}],
    indirect=True,
)
@pytest.mark.parametrize("validating_httpserver", [{"app": ContentServer}], indirect=True)
async def test_client_failure(sending_elasticapm_client, caplog):
    sending_elasticapm_client.httpserver.code = 400
    sending_elasticapm_client.httpserver.content = "Go away"

    # test error
    with caplog.at_level("ERROR", "elasticapm.transport"):
        sending_elasticapm_client.capture_message("foo", handled=False)
        tasks = asyncio.Task.all_tasks()
        task = next(t for t in tasks if t is not asyncio.Task.current_task())
        with pytest.raises(TransportException):
            await task
    assert sending_elasticapm_client._transport.state.did_fail()
    assert "400" in caplog.records[0].message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "elasticapm_client", [{"transport_class": "elasticapm.transport.asyncio.AsyncioHTTPTransport"}], indirect=True
)
@asynctest.patch("elasticapm.transport.asyncio.AsyncioHTTPTransport._send")
async def test_client_failure_stdlib_exception(mock_send, elasticapm_client, caplog):
    mock_send.side_effect = RuntimeError("oops")
    with caplog.at_level("ERROR", "elasticapm.transport"):
        elasticapm_client.capture_message("foo", handled=False)
        tasks = asyncio.Task.all_tasks()
        task = next(t for t in tasks if t is not asyncio.Task.current_task())
        with pytest.raises(RuntimeError):
            await task
    assert elasticapm_client._transport.state.did_fail()
    assert "oops" in caplog.records[0].message


@pytest.mark.asyncio
async def test_client_send_timer():
    from elasticapm.contrib.asyncio.client import Client, AsyncTimer

    client = Client(transport_class="elasticapm.transport.asyncio.AsyncioHTTPTransport")

    assert client._send_timer is None

    client.begin_transaction("test_type")
    client.end_transaction("test")

    assert isinstance(client._send_timer, AsyncTimer)
    assert client._send_timer.interval == 5000

    client.close()
