#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

async_asgi_testclient = pytest.importorskip("async_asgi_testclient")  # isort:skip

from elasticapm.conf import constants
from elasticapm.contrib.asgi import ASGITracingMiddleware
from tests.contrib.asgi.app import app

pytestmark = pytest.mark.asgi


@pytest.fixture(scope="function")
def instrumented_app(elasticapm_client):
    return ASGITracingMiddleware(app)


@pytest.mark.asyncio
async def test_transaction_span(instrumented_app, elasticapm_client):
    async with async_asgi_testclient.TestClient(instrumented_app) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.text == "OK"

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    assert len(elasticapm_client.events[constants.SPAN]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    span = elasticapm_client.events[constants.SPAN][0]
    assert transaction["name"] == "GET unknown route"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["context"]["request"]["url"]["full"] == "/"
    assert transaction["context"]["response"]["status_code"] == 200

    assert span["name"] == "sleep"
    assert span["outcome"] == "success"
    assert span["sync"] == False


@pytest.mark.asyncio
async def test_transaction_ignore_url(instrumented_app, elasticapm_client):
    elasticapm_client.config.update("1", transaction_ignore_urls="/foo*")

    async with async_asgi_testclient.TestClient(instrumented_app) as client:
        resp = await client.get("/foo")
        assert resp.status_code == 200
        assert resp.text == "foo"

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 0


@pytest.mark.asyncio
async def test_transaction_headers(instrumented_app, elasticapm_client):
    elasticapm_client.config.update("1", capture_headers="true")

    async with async_asgi_testclient.TestClient(instrumented_app) as client:
        resp = await client.get("/foo", headers={"baz": "bazzinga"})
        assert resp.status_code == 200
        assert resp.text == "foo"

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["context"]["request"]["headers"]["baz"] == "bazzinga"
    assert transaction["context"]["response"]["headers"]["foo"] == "bar"

    elasticapm_client.config.update("1", capture_headers="false")

    async with async_asgi_testclient.TestClient(instrumented_app) as client:
        resp = await client.get("/foo", headers={"baz": "bazzinga"})
        assert resp.status_code == 200
        assert resp.text == "foo"

    transaction = elasticapm_client.events[constants.TRANSACTION][1]
    assert "headers" not in transaction["context"]["request"]
    assert "headers" not in transaction["context"]["response"]


@pytest.mark.asyncio
async def test_transaction_body(instrumented_app, elasticapm_client):
    elasticapm_client.config.update("1", capture_body="transactions")

    async with async_asgi_testclient.TestClient(instrumented_app) as client:
        resp = await client.post("/", data="foo")
        assert resp.status_code == 200
        assert resp.text == "OK"

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert "body" in transaction["context"]["request"]
    assert transaction["context"]["request"]["body"] == "foo"


# for some reason, exceptions don't seem to bubble up to our middleware with the two ASGI
# frameworks I tested (Quart, Sanic)

# @pytest.mark.asyncio
# async def test_transaction_exception(instrumented_app, elasticapm_client):
#     async with async_asgi_testclient.TestClient(instrumented_app) as client:
#         resp = await client.get("/boom")
#         assert resp.status_code == 500
#
#     assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
#
#     transaction = elasticapm_client.events[constants.TRANSACTION][0]
#     assert transaction["name"] == "GET unknown route"
#     assert transaction["result"] == "HTTP 5xx"
#     # assert transaction["outcome"] == "failure"
#
#     assert len(elasticapm_client.events[constants.ERROR]) == 1
#     error = elasticapm_client.events[constants.ERROR][0]
#     pass
