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

import pytest
import urllib3

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm.utils.compat import urlparse
from elasticapm.utils.disttracing import TraceParent


def test_urllib3(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = "GET {0}".format(parsed_url.netloc)
    with capture_span("test_name", "test_type"):
        pool = urllib3.PoolManager(timeout=0.1)

        url = "http://{0}/hello_world".format(parsed_url.netloc)
        r = pool.request("GET", url)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_name", expected_sig}

    assert {t["name"] for t in spans} == expected_signatures

    assert len(spans) == 2

    assert spans[0]["name"] == expected_sig
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert spans[0]["context"]["http"]["url"] == url
    assert spans[0]["parent_id"] == spans[1]["id"]

    assert spans[1]["name"] == "test_name"
    assert spans[1]["type"] == "test_type"
    assert spans[1]["parent_id"] == transactions[0]["id"]


def test_trace_parent_propagation_sampled(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction")
    pool = urllib3.PoolManager(timeout=0.1)
    r = pool.request("GET", url)
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_trace_parent_propagation_unsampled(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    pool = urllib3.PoolManager(timeout=0.1)
    r = pool.request("GET", url)
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert not spans

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    assert trace_parent.span_id == transaction_object.id
    assert not trace_parent.trace_options.recorded


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 1}], indirect=True)
def test_span_only_dropped(instrument, elasticapm_client, waiting_httpserver):
    """test that urllib3 instrumentation does not fail if no parent span can be found"""
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction_object = elasticapm_client.begin_transaction("transaction")
    for i in range(2):
        with capture_span("test", "test"):
            pool = urllib3.PoolManager(timeout=0.1)
            pool.request("GET", url)
    elasticapm_client.end_transaction("bla", "OK")
    trace_parent_1 = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    trace_parent_2 = TraceParent.from_string(waiting_httpserver.requests[1].headers[constants.TRACEPARENT_HEADER_NAME])

    assert trace_parent_1.span_id != transaction_object.id
    # second request should use transaction id as span id because there is no span
    assert trace_parent_2.span_id == transaction_object.id


def test_url_sanitization(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    url = url.replace("http://", "http://user:pass@")
    transaction_object = elasticapm_client.begin_transaction("transaction")
    pool = urllib3.PoolManager(timeout=0.1)
    r = pool.request("GET", url)
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]

    assert "pass" not in span["context"]["http"]["url"]
