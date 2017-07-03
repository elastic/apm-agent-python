import mock
import pytest
import urllib3.poolmanager
from urllib3.exceptions import MaxRetryError, TimeoutError
from urllib3_mock import Responses

from opbeat.transport.base import TransportException
from opbeat.transport.http_urllib3 import (AsyncUrllib3Transport,
                                           Urllib3Transport)

try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse



responses = Responses('urllib3')

@responses.activate
def test_send():
    transport = Urllib3Transport(urlparse.urlparse('http://localhost'))
    responses.add('POST', '/', status=202,
                  adding_headers={'Location': 'http://example.com/foo'})
    url = transport.send('x', {})
    assert url == 'http://example.com/foo'


@responses.activate
def test_timeout():
    transport = Urllib3Transport(urlparse.urlparse('http://localhost'))
    responses.add('POST', '/', status=202,
                  body=MaxRetryError(None, None, reason=TimeoutError()))
    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    assert 'timeout' in str(exc_info.value)


@responses.activate
def test_http_error():
    url, status, body = (
        'http://localhost:9999', 418, 'Nothing'
    )
    transport = Urllib3Transport(urlparse.urlparse(url))
    responses.add('POST', '/', status=status, body=body)

    with pytest.raises(TransportException) as exc_info:
        transport.send('x', {})
    for val in (status, body):
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
