import socket

import mock
import pytest

from elasticapm.transport.base import TransportException
from elasticapm.transport.http import HTTPTransport
from elasticapm.utils import compat


def test_send(httpserver):
    httpserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    transport = HTTPTransport(compat.urlparse.urlparse(httpserver.url))
    url = transport.send(compat.b('x'), {})
    assert url == 'http://example.com/foo'


@mock.patch('elasticapm.transport.http.urlopen')
def test_timeout(mock_urlopen):
    transport = HTTPTransport(compat.urlparse.urlparse('http://localhost:9999'))
    mock_urlopen.side_effect = socket.timeout()
    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    assert 'timeout' in str(exc_info.value)


def test_http_error(httpserver):
    httpserver.serve_content(code=418, content="I'm a teapot")
    transport = HTTPTransport(compat.urlparse.urlparse(httpserver.url))
    with pytest.raises(TransportException) as exc_info:
        transport.send(compat.b('x'), {})
    for val in (httpserver.url, 418, "I'm a teapot"):
        assert str(val) in str(exc_info.value)


@mock.patch('elasticapm.transport.http.urlopen')
def test_generic_error(mock_urlopen):
    url, status, message, body = (
        'http://localhost:9999', 418, "I'm a teapot", 'Nothing'
    )
    transport = HTTPTransport(compat.urlparse.urlparse(url))
    mock_urlopen.side_effect = Exception('Oopsie')
    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    assert 'Oopsie' in str(exc_info.value)
