import pytest  # isort:skip

pytest.importorskip("requests")  # isort:skip

import requests
from requests.exceptions import InvalidURL, MissingSchema

from elasticapm.conf import constants
from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.requests


def test_requests_instrumentation(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        requests.get(url, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert url == spans[0]["context"]["http"]["url"]

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]

    # this should be the span id of `requests`, not of urllib3
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_requests_instrumentation_via_session(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        s = requests.Session()
        s.get(url, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert url == spans[0]["context"]["http"]["url"]

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]

    # this should be the span id of `requests`, not of urllib3
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_requests_instrumentation_via_prepared_request(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        r = requests.Request("get", url)
        pr = r.prepare()
        s = requests.Session()
        s.send(pr, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert spans[0]["name"].startswith("GET 127.0.0.1:")
    assert url == spans[0]["context"]["http"]["url"]

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers
    trace_parent = TraceParent.from_string(waiting_httpserver.requests[0].headers[constants.TRACEPARENT_HEADER_NAME])
    assert trace_parent.trace_id == transactions[0]["trace_id"]

    # this should be the span id of `requests`, not of urllib3
    assert trace_parent.span_id == spans[0]["id"]
    assert trace_parent.trace_options.recorded


def test_requests_instrumentation_malformed_none(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(MissingSchema):
            requests.get(None)


def test_requests_instrumentation_malformed_schema(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(MissingSchema):
            requests.get("")


def test_requests_instrumentation_malformed_path(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(InvalidURL):
            requests.get("http://")
