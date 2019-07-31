#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import os

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


def test_ssl_cert_pinning(waiting_httpsserver):
    waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    transport = Transport(
        waiting_httpsserver.url, server_cert=os.path.join(cur_dir, "..", "ca/server.pem"), verify_server_cert=True
    )
    try:
        url = transport.send(compat.b("x"))
        assert url == "https://example.com/foo"
    finally:
        transport.close()


def test_ssl_cert_pinning_fails(waiting_httpsserver):
    if compat.PY3:
        waiting_httpsserver.serve_content(code=202, content="", headers={"Location": "https://example.com/foo"})
        url = waiting_httpsserver.url
    else:
        # if we use the local test server here, execution blocks somewhere deep in OpenSSL on Python 2.7, presumably
        # due to a threading issue that has been fixed in later versions. To avoid that, we have to commit a minor
        # cardinal sin here and do an outside request to https://example.com (which will also fail the fingerprint
        # assertion).
        #
        # May the Testing Goat have mercy on our souls.
        url = "https://example.com"
    transport = Transport(
        url, server_cert=os.path.join(os.path.dirname(__file__), "wrong_cert.pem"), verify_server_cert=True
    )
    with pytest.raises(TransportException) as exc_info:
        transport.send(compat.b("x"))
    transport.close()

    assert "Fingerprints did not match" in exc_info.value.args[0]
