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

pytest.importorskip("httplib2")  # isort:skip

import httplib2

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.httplib2


@pytest.mark.parametrize("args", [(), ("GET",), ("GET", None, {}), ("GET", None, None)])
def test_httplib2_instrumentation(instrument, elasticapm_client, waiting_httpserver, args):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        httplib2.Http().request(url, *args)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert url == spans[0]["context"]["http"]["url"]
    assert 200 == spans[0]["context"]["http"]["status_code"]
    assert spans[0]["context"]["destination"]["service"] == {
        "name": "",
        "resource": "127.0.0.1:%d" % parsed_url.port,
        "type": "",
    }
    assert spans[0]["outcome"] == "success"

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(
        waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME],
        tracestate_string=waiting_httpserver.requests[0].headers[constants.TRACESTATE_HEADER_NAME],
    )
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    # Check that sample_rate was correctly placed in the tracestate
    assert constants.TRACESTATE.SAMPLE_RATE in trace_parent.tracestate_dict


@pytest.mark.parametrize("status_code", [400, 500])
def test_httplib2_instrumentation_error(instrument, elasticapm_client, waiting_httpserver, status_code):
    waiting_httpserver.serve_content("", code=status_code)
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        httplib2.Http().request(url, "GET")
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert url == spans[0]["context"]["http"]["url"]
    assert status_code == spans[0]["context"]["http"]["status_code"]
    assert spans[0]["context"]["destination"]["service"] == {
        "name": "",
        "resource": "127.0.0.1:%d" % parsed_url.port,
        "type": "",
    }
    assert spans[0]["outcome"] == "failure"


@pytest.mark.parametrize(
    "is_sampled", [pytest.param(True, id="is_sampled-True"), pytest.param(False, id="is_sampled-False")]
)
def test_tracestate_propagation(instrument, elasticapm_client, waiting_httpserver, is_sampled):
    traceparent = TraceParent.from_string(
        "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03", "foo=bar,baz=bazzinga"
    )

    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    transaction_object = elasticapm_client.begin_transaction("transaction", trace_parent=traceparent)
    transaction_object.is_sampled = is_sampled
    httplib2.Http().request(url, "GET")
    elasticapm_client.end_transaction("MyView")
    headers = waiting_httpserver.requests[0].headers
    assert headers[constants.TRACESTATE_HEADER_NAME] == "foo=bar,baz=bazzinga"
