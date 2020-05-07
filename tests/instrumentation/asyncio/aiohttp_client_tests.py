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
yarl = pytest.importorskip("yarl")  # isort:skip

from elasticapm.conf import constants
from elasticapm.utils.disttracing import TraceParent

pytestmark = [pytest.mark.asyncio, pytest.mark.aiohttp]


@pytest.mark.parametrize("use_yarl", [True, False])
async def test_http_get(instrument, event_loop, elasticapm_client, waiting_httpserver, use_yarl):
    assert event_loop.is_running()
    elasticapm_client.begin_transaction("test")

    url = waiting_httpserver.url
    url = yarl.URL(url) if use_yarl else url

    async with aiohttp.ClientSession() as session:
        async with session.get(waiting_httpserver.url) as resp:
            status = resp.status
            text = await resp.text()

    elasticapm_client.end_transaction()
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "GET %s:%s" % waiting_httpserver.server_address
    assert span["type"] == "external"
    assert span["subtype"] == "http"
    assert span["sync"] is False
    assert span["context"]["http"]["url"] == waiting_httpserver.url
    assert spans[0]["context"]["destination"]["service"] == {
        "name": "http://127.0.0.1:%d" % waiting_httpserver.server_address[1],
        "resource": "127.0.0.1:%d" % waiting_httpserver.server_address[1],
        "type": "external",
    }


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        pytest.param({"use_elastic_traceparent_header": True}, id="use_elastic_traceparent_header-True"),
        pytest.param({"use_elastic_traceparent_header": False}, id="use_elastic_traceparent_header-False"),
    ],
    indirect=True,
)
async def test_trace_parent_propagation_sampled(instrument, event_loop, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction")
    async with aiohttp.ClientSession() as session:
        async with session.get(waiting_httpserver.url) as resp:
            status = resp.status
            text = await resp.text()
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    headers = waiting_httpserver.requests[0].headers
    assert constants.TRACEPARENT_HEADER_NAME in headers
    trace_parent = TraceParent.from_string(headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded

    if elasticapm_client.config.use_elastic_traceparent_header:
        assert constants.TRACEPARENT_LEGACY_HEADER_NAME in headers
        assert headers[constants.TRACEPARENT_HEADER_NAME] == headers[constants.TRACEPARENT_LEGACY_HEADER_NAME]
    else:
        assert constants.TRACEPARENT_LEGACY_HEADER_NAME not in headers


@pytest.mark.parametrize("sampled", [True, False])
async def test_trace_parent_propagation_sampled_headers_none(
    instrument, event_loop, elasticapm_client, waiting_httpserver, sampled
):
    """
    Test that we don't blow up if headers are explicitly set to None
    """
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction = elasticapm_client.begin_transaction("transaction")
    transaction.is_sampled = sampled
    async with aiohttp.ClientSession() as session:
        async with session.get(waiting_httpserver.url, headers=None) as resp:
            status = resp.status
            text = await resp.text()
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    headers = waiting_httpserver.requests[0].headers
    assert constants.TRACEPARENT_HEADER_NAME in headers
    trace_parent = TraceParent.from_string(headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    if sampled:
        assert trace_parent.span_id == spans[0]["id"]
    else:
        assert trace_parent.span_id == transactions[0]["id"]


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        pytest.param({"use_elastic_traceparent_header": True}, id="use_elastic_traceparent_header-True"),
        pytest.param({"use_elastic_traceparent_header": False}, id="use_elastic_traceparent_header-False"),
    ],
    indirect=True,
)
async def test_trace_parent_propagation_unsampled(instrument, event_loop, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    async with aiohttp.ClientSession() as session:
        async with session.get(waiting_httpserver.url) as resp:
            status = resp.status
            text = await resp.text()
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert not spans

    headers = waiting_httpserver.requests[0].headers
    assert constants.TRACEPARENT_HEADER_NAME in headers
    trace_parent = TraceParent.from_string(headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == transaction_object.id
    assert not trace_parent.trace_options.recorded

    if elasticapm_client.config.use_elastic_traceparent_header:
        assert constants.TRACEPARENT_LEGACY_HEADER_NAME in headers
        assert headers[constants.TRACEPARENT_HEADER_NAME] == headers[constants.TRACEPARENT_LEGACY_HEADER_NAME]
    else:
        assert constants.TRACEPARENT_LEGACY_HEADER_NAME not in headers


@pytest.mark.parametrize(
    "is_sampled", [pytest.param(True, id="is_sampled-True"), pytest.param(False, id="is_sampled-False")]
)
async def test_tracestate_propagation(instrument, event_loop, elasticapm_client, waiting_httpserver, is_sampled):
    traceparent = TraceParent.from_string(
        "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03", "foo=bar,baz=bazzinga"
    )

    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction_object = elasticapm_client.begin_transaction("transaction", trace_parent=traceparent)
    transaction_object.is_sampled = is_sampled
    async with aiohttp.ClientSession() as session:
        async with session.get(waiting_httpserver.url) as resp:
            status = resp.status
            text = await resp.text()
    elasticapm_client.end_transaction("MyView")
    headers = waiting_httpserver.requests[0].headers
    assert headers[constants.TRACESTATE_HEADER_NAME] == "foo=bar,baz=bazzinga"
