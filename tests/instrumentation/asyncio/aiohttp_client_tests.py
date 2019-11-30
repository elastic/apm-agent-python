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

import aiohttp
import pytest

from elasticapm.conf import constants
from elasticapm.utils.disttracing import TraceParent

pytestmark = [pytest.mark.asyncio, pytest.mark.aiohttp]


async def test_http_get(instrument, event_loop, elasticapm_client, waiting_httpserver):
    assert event_loop.is_running()
    elasticapm_client.begin_transaction("test")

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

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


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

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == transaction_object.id
    assert not trace_parent.trace_options.recorded
