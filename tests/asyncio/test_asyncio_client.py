import asyncio
import sys
from urllib.parse import urlparse

import mock
import pytest

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5),
                                reason='python3.5+ requried for asyncio')


class MockTransport(mock.MagicMock):
    async_mode = False

    def __init__(self, url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.url = url

    async def send(self, data, headers, timeout):
        from elasticapm.transport.base import TransportException
        self.data = data
        if self.url == urlparse('http://error'):
            raise TransportException('', data, False)
        await asyncio.sleep(0.0001)


class DummyTransport:
    async_mode = False

    def __init__(self, *args, **kwargs):
        pass

    async def send(self, data, headers, timeout):
        return

    def close(self):
        pass


@pytest.mark.asyncio
async def test_client_success():
    from elasticapm.contrib.asyncio import Client

    client = Client(
        server_url='http://localhost',
        service_name='service_name',
        secret_token='secret',
        transport_class='.'.join(
            (__name__, MockTransport.__name__)),
    )
    client.send(client.config.server_url, foo='bar')
    tasks = asyncio.Task.all_tasks()
    task = next(t for t in tasks if t is not asyncio.Task.current_task())
    await task
    assert client.state.status == 1
    transport = client._get_transport(urlparse('http://localhost'))
    assert transport.data == client.encode({'foo': 'bar'})


@pytest.mark.asyncio
async def test_client_failure():
    from elasticapm.contrib.asyncio import Client
    from elasticapm.transport.base import TransportException

    client = Client(
        server_url='http://error',
        service_name='service_name',
        secret_token='secret',
        transport_class='.'.join(
            (__name__, MockTransport.__name__)),
    )
    client.send(client.config.server_url, foo='bar')
    tasks = asyncio.Task.all_tasks()
    task = next(t for t in tasks if t is not asyncio.Task.current_task())
    with pytest.raises(TransportException):
        await task
    assert client.state.status == 0


@pytest.mark.asyncio
async def test_client_failure_stdlib_exception(mocker):
    from elasticapm.contrib.asyncio import Client
    from elasticapm.transport.base import TransportException

    client = Client(
        server_url='http://elastic.co',
        service_name='service_name',
        secret_token='secret',
        async_mode=False,
        transport_class='elasticapm.transport.asyncio.AsyncioHTTPTransport',
    )
    mock_client = mocker.Mock()
    mock_client.post = mocker.Mock(side_effect=RuntimeError('oops'))
    transport = client._get_transport(urlparse('http://elastic.co'))
    transport.client = mock_client
    client.send(client.config.server_url, foo='bar')
    tasks = asyncio.Task.all_tasks()
    task = next(t for t in tasks if t is not asyncio.Task.current_task())
    with pytest.raises(TransportException):
        await task
    assert client.state.status == 0


@pytest.mark.asyncio
async def test_client_send_timer():
    from elasticapm.contrib.asyncio.client import Client, AsyncTimer

    client = Client(
        transport_class='tests.asyncio.test_asyncio_client.DummyTransport'
    )

    assert client._send_timer is None

    client.begin_transaction('test_type')
    client.end_transaction('test')

    assert isinstance(client._send_timer, AsyncTimer)
    assert client._send_timer.interval == 5

    client.close()
