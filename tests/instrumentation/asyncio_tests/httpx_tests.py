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

pytest.importorskip("httpx")  # isort:skip

import httpx
from httpx import InvalidURL

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.httpx


async def test_httpx_instrumentation(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction.test")
    async with async_capture_span("test_request", "test"):
        async with httpx.AsyncClient() as client:
            await client.get(url, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert spans[0]["outcome"] == "success"
    assert url == spans[0]["context"]["http"]["url"]
    assert spans[0]["context"]["destination"]["service"] == {
        "name": "http://127.0.0.1:%d" % parsed_url.port,
        "resource": "127.0.0.1:%d" % parsed_url.port,
        "type": "external",
    }

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]

    # this should be the span id of `httpx`, not of urllib3
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


async def test_httpx_instrumentation_string_url(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction.test")
    async with async_capture_span("test_request", "test"):
        async with httpx.AsyncClient() as client:
            await client.get(url, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert url == spans[0]["context"]["http"]["url"]

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]

    # this should be the span id of `httpx`, not of urllib3
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


async def test_httpx_instrumentation_malformed_empty(instrument, elasticapm_client):
    try:
        from httpx._exceptions import UnsupportedProtocol
    except ImportError:
        pytest.skip("Test requires HTTPX 0.14+")
    elasticapm_client.begin_transaction("transaction.test")
    async with async_capture_span("test_request", "test"):
        with pytest.raises(UnsupportedProtocol):
            httpx.get("")


async def test_httpx_instrumentation_malformed_path(instrument, elasticapm_client):
    try:
        from httpx._exceptions import LocalProtocolError
    except ImportError:
        pytest.skip("Test requires HTTPX 0.14+")
    elasticapm_client.begin_transaction("transaction.test")
    async with async_capture_span("test_request", "test"):
        async with httpx.AsyncClient() as client:
            with pytest.raises(LocalProtocolError):
                await client.get("http://")


async def test_url_sanitization(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    url = url.replace("http://", "http://user:pass@")
    transaction_object = elasticapm_client.begin_transaction("transaction")
    async with httpx.AsyncClient() as client:
        await client.get(url)
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]

    assert "pass" not in span["context"]["http"]["url"]
    assert constants.MASK in span["context"]["http"]["url"]


@pytest.mark.parametrize("status_code", [400, 500])
async def test_httpx_error(instrument, elasticapm_client, waiting_httpserver, status_code):
    waiting_httpserver.serve_content("", code=status_code)
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = "GET {0}".format(parsed_url.netloc)
    url = "http://{0}/hello_world".format(parsed_url.netloc)
    async with async_capture_span("test_name", "test_type"):
        async with httpx.AsyncClient() as client:
            await client.get(url, allow_redirects=False)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] == expected_sig
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert spans[0]["context"]["http"]["url"] == url
    assert spans[0]["context"]["http"]["status_code"] == status_code
    assert spans[0]["outcome"] == "failure"
