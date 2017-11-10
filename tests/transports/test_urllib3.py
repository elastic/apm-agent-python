import mock
import pytest
import urllib3.poolmanager
from urllib3.exceptions import MaxRetryError, TimeoutError
from urllib3_mock import Responses

from elasticapm.transport.base import TransportException
from elasticapm.transport.http_urllib3 import Urllib3Transport
from elasticapm.utils import compat

try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse


responses = Responses('urllib3')


def test_send(httpserver):
    httpserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    transport = Urllib3Transport(urlparse.urlparse(httpserver.url))
    url = transport.send(compat.b('x'), {})
    assert url == 'http://example.com/foo'


@responses.activate
def test_timeout():
    transport = Urllib3Transport(urlparse.urlparse('http://localhost'))
    responses.add('POST', '/', status=202,
                  body=MaxRetryError(None, None, reason=TimeoutError()))
    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    assert 'timeout' in str(exc_info.value)


def test_http_error(httpserver):
    httpserver.serve_content(code=418, content="I'm a teapot")
    transport = Urllib3Transport(urlparse.urlparse(httpserver.url))

    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    for val in (418, "I'm a teapot"):
        assert str(val) in str(exc_info.value)


@responses.activate
def test_generic_error():
    url, status, message, body = (
        'http://localhost:9999', 418, "I'm a teapot", 'Nothing'
    )
    transport = Urllib3Transport(urlparse.urlparse(url))
    responses.add('POST', '/', status=status, body=Exception('Oopsie'))
    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    assert 'Oopsie' in str(exc_info.value)


def test_http_proxy_environment_variable():
    with mock.patch.dict('os.environ', {'HTTP_PROXY': 'http://example.com'}):
        transport = Urllib3Transport(urlparse.urlparse('http://localhost:9999'))
        assert isinstance(transport.http, urllib3.ProxyManager)


def test_https_proxy_environment_variable():
    with mock.patch.dict('os.environ', {'HTTPS_PROXY': 'https://example.com'}):
        transport = Urllib3Transport(urlparse.urlparse('http://localhost:9999'))
        assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)


def test_https_proxy_environment_variable_is_preferred():
    with mock.patch.dict('os.environ', {'HTTPS_PROXY': 'https://example.com',
                                        'HTTP_PROXY': 'http://example.com'}):
        transport = Urllib3Transport(urlparse.urlparse('http://localhost:9999'))
        assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)
        assert transport.http.proxy.scheme == 'https'


def test_header_encodings():
    """
    Tests that headers are encoded as bytestrings. If they aren't,
    urllib assumes it needs to encode the data as well, which is already a zlib
    encoded bytestring, and explodes.
    """
    headers = {
        compat.text_type('X'): compat.text_type('V')
    }
    transport = Urllib3Transport(urlparse.urlparse('http://localhost:9999'))

    with mock.patch('elasticapm.transport.http_urllib3.urllib3.PoolManager.urlopen') as mock_urlopen:
        mock_urlopen.return_value = mock.Mock(status=202)
        transport.send('', headers)
    _, args, kwargs = mock_urlopen.mock_calls[0]
    if compat.PY2:
        assert isinstance(args[1], compat.binary_type)
    for k, v in kwargs['headers'].items():
        assert isinstance(k, compat.binary_type)
        assert isinstance(v, compat.binary_type)
