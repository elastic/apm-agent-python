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

import pytest
import webob

from elasticapm.conf.constants import ERROR
from elasticapm.middleware import ElasticAPM


def example_app(environ, start_response):
    raise ValueError("hello world")


def test_error_handler(elasticapm_client):
    middleware = ElasticAPM(example_app, client=elasticapm_client)

    request = webob.Request.blank("/an-error?foo=bar")
    response = middleware(request.environ, lambda *args: None)

    with pytest.raises(ValueError):
        list(response)

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events[ERROR][0]

    assert "exception" in event
    exc = event["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "ValueError: hello world"

    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["url"]["full"] == "http://localhost/an-error?foo=bar"
    assert request["url"]["search"] == "?foo=bar"
    assert request["method"] == "GET"
    headers = request["headers"]
    assert "host" in headers, headers.keys()
    assert headers["host"] == "localhost:80"
    env = request["env"]
    assert "SERVER_NAME" in env, env.keys()
    assert env["SERVER_NAME"] == "localhost"
    assert "SERVER_PORT" in env, env.keys()
    assert env["SERVER_PORT"] == "80"
