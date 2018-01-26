import asyncio
import sys
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.skipif(sys.version_info < (3, 5),
                                reason='python3.5+ requried for asyncio')

@pytest.fixture
def mock_client(mocker):
    mock_client = mocker.MagicMock()
    mock_client.config.server_timeout = None
    response = mocker.MagicMock()

    async def read():
        return mock_client.body

    response.read = read


    class fake_post:
        async def __aenter__(self, *args, **kwargs):
            response.status = mock_client.status
            response.headers = mock_client.headers
            if mock_client.config.server_timeout:
                await asyncio.sleep(mock_client.config.server_timeout)
            return response

        async def __aexit__(self, *args):
            pass

        def __init__(self, *args, **kwargs):
            mock_client.args = args
            mock_client.kwargs = kwargs


    mock_client.post = mocker.Mock(side_effect=fake_post)
    return mock_client


@pytest.mark.asyncio
async def test_send(mock_client):
    from elasticapm.transport.asyncio import AsyncioHTTPTransport
    transport = AsyncioHTTPTransport(urlparse('http://localhost:9999'))

    mock_client.status = 202
    mock_client.headers = {'Location': 'http://example.com/foo'}
    transport.client = mock_client

    url = await transport.send(b'data', {'a': 'b'}, timeout=2)
    assert url == 'http://example.com/foo'
    assert mock_client.args == ('http://localhost:9999',)
    assert mock_client.kwargs == {'headers': {'a': 'b'},
                                  'data': b'data'}


@pytest.mark.asyncio
async def test_send_not_found(mock_client):
    from elasticapm.transport.asyncio import AsyncioHTTPTransport
    from elasticapm.transport.base import TransportException

    transport = AsyncioHTTPTransport(urlparse('http://localhost:9999'))

    mock_client.status = 404
    mock_client.headers = {}
    mock_client.body = b'Not Found'
    transport.client = mock_client

    with pytest.raises(TransportException) as excinfo:
        await transport.send(b'data', {}, timeout=2)
    assert 'Not Found' in str(excinfo.value)
    assert excinfo.value.data == b'data'


@pytest.mark.asyncio
async def test_send_timeout(mock_client):
    from elasticapm.transport.asyncio import AsyncioHTTPTransport
    from elasticapm.transport.base import TransportException

    transport = AsyncioHTTPTransport(urlparse('http://localhost:9999'))

    mock_client.config.server_timeout = 0.1
    transport.client = mock_client

    with pytest.raises(TransportException) as excinfo:
        await transport.send(b'data', {}, timeout=0.0001)
    assert 'Connection to APM Server timed out' in str(excinfo.value)


@pytest.mark.asyncio
async def test_ssl_verify_fails(httpsserver):
    from elasticapm.transport.asyncio import AsyncioHTTPTransport
    from elasticapm.transport.base import TransportException

    httpsserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    transport = AsyncioHTTPTransport(urlparse(httpsserver.url))
    with pytest.raises(TransportException) as exc_info:
        await transport.send(b'x', {})
    assert 'CERTIFICATE_VERIFY_FAILED' in str(exc_info)


@pytest.mark.asyncio
async def test_ssl_verify_disable(httpsserver):
    from elasticapm.transport.asyncio import AsyncioHTTPTransport

    httpsserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    transport = AsyncioHTTPTransport(urlparse(httpsserver.url), verify_server_cert=False)
    url = await transport.send(b'x', {})
    assert url == 'http://example.com/foo'
