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

import pytest  # isort:skip

sanic = pytest.importorskip("sanic")  # isort:skip

from elasticapm.conf import constants

pytestmark = [pytest.mark.sanic]  # isort:skip


def test_get(sanic_app, elasticapm_client):
    source_request, response = sanic_app.test_client.get(
        "/",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )  # type: sanic.response.HttpResponse

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    for field, value in {
        "name": "GET /",
        "result": "HTTP 2xx",
        "outcome": "success",
        "type": "request",
    }.items():
        assert transaction[field] == value

    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": f"127.0.0.1", "encrypted": False}

    assert span["name"] == "test"


def test_capture_exception(sanic_app, elasticapm_client):
    _, _ = sanic_app.test_client.get(
        "/capture-exception",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )

    assert len(elasticapm_client.events[constants.ERROR]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    for field, value in {
        "name": "GET /capture-exception",
        "result": "HTTP 5xx",
        "outcome": "failure",
        "type": "request",
    }.items():
        assert transaction[field] == value


def test_unhandled_exception_capture(sanic_app, elasticapm_client):
    _, resp = sanic_app.test_client.post(
        "/v1/apm/unhandled-exception",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )
    assert len(elasticapm_client.events[constants.ERROR]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    for field, value in {
        "name": "POST /v1/apm/unhandled-exception",
        "result": "HTTP 5xx",
        "outcome": "failure",
        "type": "request",
    }.items():
        assert transaction[field] == value
