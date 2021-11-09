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

aiohttp = pytest.importorskip("aiohttp")  # isort:skip

import mock
from multidict import MultiDict

import elasticapm
from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.aiohttp import ElasticAPM
from elasticapm.contrib.aiohttp.middleware import AioHttpTraceParent
from elasticapm.utils.disttracing import TraceParent

pytestmark = [pytest.mark.aiohttp]


@pytest.fixture
def aioeapm(elasticapm_client):
    async def hello(request):
        with async_capture_span("test"):
            pass
        return aiohttp.web.Response(body=b"Hello, world")

    async def boom(request):
        raise aiohttp.web.HTTPInternalServerError(headers={"boom": "boom"})

    async def raise_ok(request):
        raise aiohttp.web.HTTPOk(body=b"a bit odd but sometimes handy")

    async def exception(request):
        raise ValueError("boom")

    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", hello)
    app.router.add_route("GET", "/hello", hello)
    app.router.add_route("GET", "/boom", boom)
    app.router.add_route("GET", "/raise/ok", raise_ok)
    app.router.add_route("GET", "/exception", exception)
    apm = ElasticAPM(app, elasticapm_client)
    yield apm

    elasticapm.uninstrument()


async def test_get(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get("/")
    assert resp.status == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "GET /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    request["method"] == "GET"
    request["socket"] == {"remote_address": "127.0.0.1"}

    assert span["name"] == "test"


async def test_transaction_ignore_urls(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get("/")
    assert resp.status == 200
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    elasticapm_client.config.update(1, transaction_ignore_urls="x")
    resp = await client.get("/")
    assert resp.status == 200
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 2
    elasticapm_client.config.update(1, transaction_ignore_urls="*,x")
    resp = await client.get("/")
    assert resp.status == 200
    # still only two transaction
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 2


@pytest.mark.parametrize(
    "url,exception",
    (("/boom", "HTTPInternalServerError"), ("/exception", "ValueError")),
)
async def test_exception(aiohttp_client, aioeapm, url, exception):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get(url)
    assert resp.status == 500

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == f"GET {url}"
    assert transaction["result"] == "HTTP 5xx"
    assert transaction["outcome"] == "failure"
    assert transaction["type"] == "request"
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}
    assert transaction["context"]["response"]["status_code"] == 500

    assert len(elasticapm_client.events[constants.ERROR]) == 1
    error = elasticapm_client.events[constants.ERROR][0]
    assert error["transaction_id"] == transaction["id"]
    assert error["exception"]["type"] == exception
    assert error["context"]["request"] == transaction["context"]["request"]


async def test_http_exception_below_500(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get("/raise/ok")
    assert resp.status == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /raise/ok"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}
    assert transaction["context"]["response"]["status_code"] == 200

    assert len(elasticapm_client.events[constants.ERROR]) == 0


async def test_capture_headers_is_dynamic(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client

    elasticapm_client.config.update("1", capture_headers=True)
    await client.get("/boom")

    elasticapm_client.config.update("2", capture_headers=False)
    await client.get("/boom")
    assert elasticapm_client.config.capture_headers is False

    assert "headers" in elasticapm_client.events[constants.TRANSACTION][0]["context"]["request"]
    assert "headers" in elasticapm_client.events[constants.TRANSACTION][0]["context"]["response"]
    assert "headers" in elasticapm_client.events[constants.ERROR][0]["context"]["request"]

    assert "headers" not in elasticapm_client.events[constants.TRANSACTION][1]["context"]["request"]
    assert "headers" not in elasticapm_client.events[constants.TRANSACTION][1]["context"]["response"]
    assert "headers" not in elasticapm_client.events[constants.ERROR][1]["context"]["request"]


async def test_traceparent_handling(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    with mock.patch(
        "elasticapm.contrib.aiohttp.middleware.TraceParent.from_string", wraps=TraceParent.from_string
    ) as wrapped_from_string:
        resp = await client.get(
            "/boom",
            headers=(
                (constants.TRACEPARENT_HEADER_NAME, "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03"),
                (constants.TRACESTATE_HEADER_NAME, "foo=bar,bar=baz"),
                (constants.TRACESTATE_HEADER_NAME, "baz=bazzinga"),
            ),
        )

    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert transaction["parent_id"] == "b7ad6b7169203331"
    assert "foo=bar,bar=baz,baz=bazzinga" in wrapped_from_string.call_args[0]


@pytest.mark.parametrize("headers,expected", ((MultiDict((("a", "1"), ("a", "2"))), "1,2"), (MultiDict(), None)))
async def test_aiohttptraceparent_merge(headers, expected):
    result = AioHttpTraceParent.merge_duplicate_headers(headers, "a")
    assert result == expected


async def test_aiohttp_transaction_ignore_urls(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get("/hello")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1

    elasticapm_client.config.update(1, transaction_ignore_urls="/*ello,/world")
    resp = await client.get("/hello")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
