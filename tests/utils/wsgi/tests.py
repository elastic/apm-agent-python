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

from __future__ import absolute_import

from elasticapm.utils.wsgi import get_environ, get_headers, get_host


def test_get_headers_tuple_as_key():
    result = dict(get_headers({("a", "tuple"): "foo"}))
    assert result == {}


def test_get_headers_coerces_http_name():
    result = dict(get_headers({"HTTP_ACCEPT": "text/plain"}))
    assert "accept" in result
    assert result["accept"] == "text/plain"


def test_get_headers_coerces_content_type():
    result = dict(get_headers({"CONTENT_TYPE": "text/plain"}))
    assert "content-type" in result
    assert result["content-type"] == "text/plain"


def test_get_headers_coerces_content_length():
    result = dict(get_headers({"CONTENT_LENGTH": "134"}))
    assert "content-length" in result
    assert result["content-length"] == "134"


def test_get_environ_has_remote_addr():
    result = dict(get_environ({"REMOTE_ADDR": "127.0.0.1"}))
    assert "REMOTE_ADDR" in result
    assert result["REMOTE_ADDR"] == "127.0.0.1"


def test_get_environ_has_server_name():
    result = dict(get_environ({"SERVER_NAME": "127.0.0.1"}))
    assert "SERVER_NAME" in result
    assert result["SERVER_NAME"] == "127.0.0.1"


def test_get_environ_has_server_port():
    result = dict(get_environ({"SERVER_PORT": 80}))
    assert "SERVER_PORT" in result
    assert result["SERVER_PORT"] == 80


def test_get_environ_hides_wsgi_input():
    result = list(get_environ({"wsgi.input": "foo"}))
    assert "wsgi.input" not in result


def test_get_host_http_x_forwarded_host():
    result = get_host({"HTTP_X_FORWARDED_HOST": "example.com"})
    assert result == "example.com"


def test_get_host_http_host():
    result = get_host({"HTTP_HOST": "example.com"})
    assert result == "example.com"


def test_get_host_http_strips_port():
    result = get_host({"wsgi.url_scheme": "http", "SERVER_NAME": "example.com", "SERVER_PORT": "80"})
    assert result == "example.com"


def test_get_host_https_strips_port():
    result = get_host({"wsgi.url_scheme": "https", "SERVER_NAME": "example.com", "SERVER_PORT": "443"})
    assert result == "example.com"


def test_get_host_http_nonstandard_port():
    result = get_host({"wsgi.url_scheme": "http", "SERVER_NAME": "example.com", "SERVER_PORT": "81"})
    assert result == "example.com:81"
