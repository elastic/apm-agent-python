import os

import mock
import pytest
import urllib3.poolmanager
from pytest_localserver.https import DEFAULT_CERTIFICATE
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
    url = transport.send(compat.b("x"))
    assert url == "http://example.com/foo"


@responses.activate
def test_timeout():
    transport = Transport("http://localhost", timeout=5)
    responses.add("POST", "/", status=202, body=MaxRetryError(None, None, reason=TimeoutError()))
    with pytest.raises(TransportException) as exc_info:
        transport.send("x")
    assert "timeout" in str(exc_info.value)


def test_http_error(waiting_httpserver):
    waiting_httpserver.serve_content(code=418, content="I'm a teapot")
    transport = Transport(waiting_httpserver.url)

    with pytest.raises(TransportException) as exc_info:
        transport.send("x")
    for val in (418, "I'm a teapot"):
        assert str(val) in str(exc_info.value)


@responses.activate
def test_generic_error():
    url, status, message, body = ("http://localhost:9999", 418, "I'm a teapot", "Nothing")
    transport = Transport(url)
    responses.add("POST", "/", status=status, body=Exception("Oopsie"))
    with pytest.raises(TransportException) as exc_info:
        transport.send("x")
    assert "Oopsie" in str(exc_info.value)


def test_http_proxy_environment_variable():
    with mock.patch.dict("os.environ", {"HTTP_PROXY": "http://example.com"}):
        transport = Transport("http://localhost:9999")
        assert isinstance(transport.http, urllib3.ProxyManager)


def test_https_proxy_environment_variable():
    with mock.patch.dict("os.environ", {"HTTPS_PROXY": "https://example.com"}):
        transport = Transport("http://localhost:9999")
        assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)


def test_https_proxy_environment_variable_is_preferred():
    with mock.patch.dict("os.environ", {"HTTPS_PROXY": "https://example.com", "HTTP_PROXY": "http://example.com"}):
        transport = Transport("http://localhost:9999")
        assert isinstance(transport.http, urllib3.poolmanager.ProxyManager)
        assert transport.http.proxy.scheme == "https"


def test_header_encodings():
    """
    Tests that headers are encoded as bytestrings. If they aren't,
    urllib assumes it needs to encode the data as well, which is already a zlib
    encoded bytestring, and explodes.
    """
    headers = {compat.text_type("X"): compat.text_type("V")}
    transport = Transport("http://localhost:9999", headers=headers)

    with mock.patch("elasticapm.transport.http.urllib3.PoolManager.urlopen") as mock_urlopen:
        mock_urlopen.return_value = mock.Mock(status=202)
        transport.send("")
    _, args, kwargs = mock_urlopen.mock_calls[0]
    if compat.PY2:
        assert isinstance(args[1], compat.binary_type)
    for k, v in kwargs["headers"].items():
        assert isinstance(k, compat.binary_type)
        assert isinstance(v, compat.binary_type)


def test_ssl_verify_fails(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "http://example.com/foo"})
    transport = Transport(waiting_httpsserver.url)
    with pytest.raises(TransportException) as exc_info:
        url = transport.send(compat.b("x"))
    assert "CERTIFICATE_VERIFY_FAILED" in str(exc_info)


@pytest.mark.filterwarnings("ignore:Unverified HTTPS")
def test_ssl_verify_disable(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
    transport = Transport(waiting_httpsserver.url, verify_server_cert=False)
    url = transport.send(compat.b("x"))
    assert url == "https://example.com/foo"


def test_ssl_cert_pinning(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
    transport = Transport(waiting_httpsserver.url, server_cert=DEFAULT_CERTIFICATE, verify_server_cert=True)
    url = transport.send(compat.b("x"))
    assert url == "https://example.com/foo"


def test_ssl_cert_pinning_fails(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
    transport = Transport(
        waiting_httpsserver.url,
        server_cert=os.path.join(os.path.dirname(__file__), "wrong_cert.pem"),
        verify_server_cert=True,
    )
    with pytest.raises(TransportException) as exc_info:
        transport.send(compat.b("x"))

    assert "Fingerprints did not match" in exc_info.value.args[0]
