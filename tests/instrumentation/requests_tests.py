import pytest
import requests
from requests.exceptions import InvalidURL, MissingSchema
from urllib3_mock import Responses

from elasticapm.traces import capture_span

try:
    from requests.packages import urllib3  # noqa
    responses = Responses('requests.packages.urllib3')
except ImportError:
    responses = Responses('urllib3')
responses.add('GET', '/', status=200, adding_headers={'Location': 'http://example.com/foo'})


def test_requests_instrumentation(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        # NOTE: The `allow_redirects` argument has to be set to `False`,
        # because mocking is done a level deeper, and the mocked response
        # from the `HTTPAdapter` is about to be used to make further
        # requests to resolve redirects, which doesn't make sense for this
        # test case.
        requests.get('http://example.com', allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']
    assert 'GET example.com' == spans[0]['name']
    assert 'http://example.com/' == spans[0]['context']['url']


def test_requests_instrumentation_via_session(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        s = requests.Session()
        s.get('http://example.com', allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']
    assert 'GET example.com' == spans[0]['name']
    assert 'http://example.com/' == spans[0]['context']['url']


def test_requests_instrumentation_via_prepared_request(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        r = requests.Request('get', 'http://example.com')
        pr = r.prepare()
        s = requests.Session()
        s.send(pr, allow_redirects=False)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']
    assert 'GET example.com' == spans[0]['name']
    assert 'http://example.com/' == spans[0]['context']['url']


def test_requests_instrumentation_malformed_none(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(MissingSchema):
            requests.get(None)


def test_requests_instrumentation_malformed_schema(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(MissingSchema):
            requests.get('')


def test_requests_instrumentation_malformed_path(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_request", "test"):
        with pytest.raises(InvalidURL):
            requests.get('http://')
