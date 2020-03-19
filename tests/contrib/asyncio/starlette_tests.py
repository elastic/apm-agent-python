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

starlette = pytest.importorskip("starlette")  # isort:skip

import mock
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.starlette import ElasticAPM
from elasticapm.utils.disttracing import TraceParent

pytestmark = [pytest.mark.starlette]


@pytest.fixture
def app(elasticapm_client):
    app = Starlette()

    @app.route("/", methods=["GET", "POST"])
    async def hi(request):
        with async_capture_span("test"):
            pass
        return PlainTextResponse("ok")

    @app.route("/raise-exception")
    async def raise_exception(request):
        raise ValueError()

    app.add_middleware(ElasticAPM, client=elasticapm_client)

    return app


def test_get(app, elasticapm_client):
    client = TestClient(app)

    response = client.get(
        "/",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "GET /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    request["method"] == "GET"
    request["socket"] == {"remote_address": "127.0.0.1", "encrypted": False}

    assert span["name"] == "test"


@pytest.mark.parametrize("elasticapm_client", [{"capture_body": "all"}], indirect=True)
def test_post(app, elasticapm_client):
    client = TestClient(app)

    response = client.post(
        "/",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
        data={"foo": "bar"},
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "POST /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    request["method"] == "GET"
    request["socket"] == {"remote_address": "127.0.0.1", "encrypted": False}
    assert request["body"]["foo"] == "bar"

    assert span["name"] == "test"


def test_exception(app, elasticapm_client):
    client = TestClient(app)

    with pytest.raises(ValueError):
        client.get(
            "/raise-exception",
            headers={
                constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
                constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
                "REMOTE_ADDR": "127.0.0.1",
            },
        )

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /raise-exception"
    assert transaction["result"] == "HTTP 5xx"
    assert transaction["type"] == "request"
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1", "encrypted": False}
    assert transaction["context"]["response"]["status_code"] == 500

    assert len(elasticapm_client.events[constants.ERROR]) == 1
    error = elasticapm_client.events[constants.ERROR][0]
    assert error["transaction_id"] == transaction["id"]
    assert error["exception"]["type"] == "ValueError"
    assert error["context"]["request"] == transaction["context"]["request"]


@pytest.mark.parametrize("header_name", [constants.TRACEPARENT_HEADER_NAME, constants.TRACEPARENT_LEGACY_HEADER_NAME])
def test_traceparent_handling(app, elasticapm_client, header_name):
    client = TestClient(app)
    with mock.patch(
        "elasticapm.contrib.flask.TraceParent.from_string", wraps=TraceParent.from_string
    ) as wrapped_from_string:
        response = client.get(
            "/",
            headers={
                header_name: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
                constants.TRACESTATE_HEADER_NAME: "foo=bar,baz=bazzinga",
            },
        )

    assert response.status_code == 200

    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert transaction["parent_id"] == "b7ad6b7169203331"
    assert "foo=bar,baz=bazzinga" in wrapped_from_string.call_args[0]
