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

from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.aiohttp import ElasticAPM
from elasticapm.contrib.aiohttp.middleware import AioHttpTraceParent
from elasticapm.utils.disttracing import TraceParent
from multidict import MultiDict

pytestmark = [pytest.mark.aiohttp]


@pytest.fixture
def aioeapm(elasticapm_client):
    async def hello(request):
        with async_capture_span("test"):
            pass
        return aiohttp.web.Response(body=b"Hello, world")

    async def boom(request):
        raise ValueError()

    app = aiohttp.web.Application()
    app.router.add_route("GET", "/", hello)
    app.router.add_route("GET", "/boom", boom)
    apm = ElasticAPM(app, elasticapm_client)
    yield apm


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
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    request["method"] == "GET"
    request["socket"] == {"remote_address": "127.0.0.1", "encrypted": False}

    assert span["name"] == "test"


async def test_exception(aiohttp_client, aioeapm):
    app = aioeapm.app
    client = await aiohttp_client(app)
    elasticapm_client = aioeapm.client
    resp = await client.get("/boom")
    assert resp.status == 500

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /boom"
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
