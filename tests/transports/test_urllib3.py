import mock
import pytest
import urllib3.poolmanager
from urllib3.exceptions import MaxRetryError, TimeoutError
from urllib3_mock import Responses

from elasticapm.transport.base import TransportException
from elasticapm.transport.http import Transport
from elasticapm.utils import compat

try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse


responses = Responses("urllib3")


def test_send(waiting_httpserver):
    waiting_httpserver.serve_content(code=202, content="", headers={"Location": "http://example.com/foo"})
    transport = Transport(waiting_httpserver.url)
    try:
        url = transport.send(compat.b("x"))
        assert url == "http://example.com/foo"
    finally:
        transport.close()


@responses.activate
def test_timeout():
    transport = Transport("http://localhost", timeout=5)
    try:
        responses.add("POST", "/", status=202, body=MaxRetryError(None, None, reason=TimeoutError()))
        with pytest.raises(TransportException) as exc_info:
            transport.send("x")
        assert "timeout" in str(exc_info.value)
    finally:
        transport.close()


def test_http_error(waiting_httpserver):
    waiting_httpserver.serve_content(code=418, content="I'm a teapot")
    transport = Transport(waiting_httpserver.url)
    try:
        with pytest.raises(TransportException) as exc_info:
            transport.send("x")
        for val in (418, "I'm a teapot"):
            assert str(val) in str(exc_info.value)
    finally:
        transport.close()


@responses.activate
def test_generic_error():
    url, status, message, body = ("http://localhost:9999", 418, "I'm a teapot", "Nothing")
    transport = Transport(url)
    responses.add("POST", "/", status=status, body=Exception("Oopsie"))
    try:
        with pytest.raises(TransportException) as exc_info:
            transport.send("x")
        assert "Oopsie" in str(exc_info.value)
    finally:
        transport.close()


def test_http_proxy_environment_variable():
    with mock.patch.dict("os.environ", {"HTTP_PROXY": "http://example.com"}):
        transport = Transport("http://localhost:9999")
        try:
            assert isinstance(transport.http, urllib3.ProxyManager)
        finally:
            transport.close()


def test_https_proxy_environment_variable():
    with mock.patch.dict("os.environ", {"HTTPS_PROXY": "https://example.com"}):
        transport = Transport("http://localhost:9999")
        try:
            assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)
        finally:
            transport.close()


def test_https_proxy_environment_variable_is_preferred():
    with mock.patch.dict("os.environ", {"HTTPS_PROXY": "https://example.com", "HTTP_PROXY": "http://example.com"}):
        transport = Transport("http://localhost:9999")
        try:
            assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)
            assert transport.http.proxy.scheme == "https"
        finally:
            transport.close()


def test_header_encodings():
    """
    Tests that headers are encoded as bytestrings. If they aren't,
    urllib assumes it needs to encode the data as well, which is already a zlib
    encoded bytestring, and explodes.
    """
    headers = {compat.text_type("X"): compat.text_type("V")}
    transport = Transport("http://localhost:9999", headers=headers)
    try:
        with mock.patch("elasticapm.transport.http.urllib3.PoolManager.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock.Mock(status=202)
            transport.send("")
        _, args, kwargs = mock_urlopen.mock_calls[0]
        if compat.PY2:
            assert isinstance(args[1], compat.binary_type)
        for k, v in kwargs["headers"].items():
            assert isinstance(k, compat.binary_type)
            assert isinstance(v, compat.binary_type)
    finally:
        transport.close()


def test_ssl_verify_fails(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "http://example.com/foo"})
    transport = Transport(waiting_httpsserver.url)
    try:
        with pytest.raises(TransportException) as exc_info:
            url = transport.send(compat.b("x"))
        assert "CERTIFICATE_VERIFY_FAILED" in str(exc_info)
    finally:
        transport.close()


@pytest.mark.filterwarnings("ignore:Unverified HTTPS")
def test_ssl_verify_disable(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
    transport = Transport(waiting_httpsserver.url, verify_server_cert=False)
    try:
        url = transport.send(compat.b("x"))
        assert url == "https://example.com/foo"
    finally:
        transport.close()
