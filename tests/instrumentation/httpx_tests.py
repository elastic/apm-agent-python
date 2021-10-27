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

httpx = pytest.importorskip("httpx")  # isort:skip

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.httpx

httpx_version = tuple(map(int, httpx.__version__.split(".")[:3]))

if httpx_version < (0, 20):
    allow_redirects = {"allow_redirects": False}
else:
    allow_redirects = {"follow_redirects": False}


def test_httpx_instrumentation(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        httpx.get(url, **allow_redirects)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert url == spans[0]["context"]["http"]["url"]
    assert spans[0]["context"]["destination"]["service"] == {
        "name": "",
        "resource": "127.0.0.1:%d" % parsed_url.port,
        "type": "",
    }

    headers = waiting_httpserver.requests[0].headers
    assert constants.TRACEPARENT_HEADER_NAME in headers
    trace_parent = TraceParent.from_string(
        headers[constants.TRACEPARENT_HEADER_NAME], tracestate_string=headers[constants.TRACESTATE_HEADER_NAME]
    )
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    # Check that sample_rate was correctly placed in the tracestate
    assert constants.TRACESTATE.SAMPLE_RATE in trace_parent.tracestate_dict

    # this should be the span id of `httpx`, not of httpcore
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_httpx_instrumentation_via_client(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        c = httpx.Client()
        c.get(url, **allow_redirects)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert url == spans[0]["context"]["http"]["url"]

    headers = waiting_httpserver.requests[0].headers
    assert constants.TRACEPARENT_HEADER_NAME in headers
    trace_parent = TraceParent.from_string(
        headers[constants.TRACEPARENT_HEADER_NAME], tracestate_string=headers[constants.TRACESTATE_HEADER_NAME]
    )
    assert trace_parent.trace_id == transactions[0]["trace_id"]
    # Check that sample_rate was correctly placed in the tracestate
    assert constants.TRACESTATE.SAMPLE_RATE in trace_parent.tracestate_dict

    # this should be the span id of `httpx`, not of httpcore
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_httpx_instrumentation_malformed_empty(instrument, elasticapm_client):
    try:
        from httpx._exceptions import UnsupportedProtocol
    except ImportError:
        pytest.skip("Test requires HTTPX 0.14+")
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(UnsupportedProtocol):
            httpx.get("")


def test_httpx_instrumentation_malformed_path(instrument, elasticapm_client):
    try:
        from httpx._exceptions import LocalProtocolError, UnsupportedProtocol
    except ImportError:
        pytest.skip("Test requires HTTPX 0.14+")
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        # raises UnsupportedProtocol since 0.18.0
        with pytest.raises((LocalProtocolError, UnsupportedProtocol)):
            httpx.get("http://")


def test_url_sanitization(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    url = url.replace("http://", "http://user:pass@")
    transaction_object = elasticapm_client.begin_transaction("transaction")
    httpx.get(url)
    elasticapm_client.end_transaction("MyView")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]

    assert "pass" not in span["context"]["http"]["url"]
    assert constants.MASK in span["context"]["http"]["url"]


@pytest.mark.parametrize("status_code", [400, 500])
def test_httpx_error(instrument, elasticapm_client, waiting_httpserver, status_code):
    waiting_httpserver.serve_content("", code=status_code)
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = compat.urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = "GET {0}".format(parsed_url.netloc)
    url = "http://{0}/hello_world".format(parsed_url.netloc)
    with capture_span("test_name", "test_type"):
        c = httpx.Client()
        c.get(url, **allow_redirects)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] == expected_sig
    assert spans[0]["type"] == "external"
    assert spans[0]["subtype"] == "http"
    assert spans[0]["context"]["http"]["url"] == url
    assert spans[0]["context"]["http"]["status_code"] == status_code
    assert spans[0]["outcome"] == "failure"


def test_httpx_streaming(instrument, elasticapm_client, waiting_httpserver):
    # client.stream passes the request as a keyword argument to the instrumented method.
    # This helps test that we can handle it both as an arg and a kwarg
    # see https://github.com/elastic/apm-agent-python/issues/1336
    elasticapm_client.begin_transaction("httpx-context-manager-client-streaming")
    client = httpx.Client()
    try:
        with client.stream("GET", url=waiting_httpserver.url) as response:
            assert response
    finally:
        client.close()
        elasticapm_client.end_transaction("httpx-context-manager-client-streaming")

    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]
    assert span["type"] == "external"
    assert span["subtype"] == "http"
