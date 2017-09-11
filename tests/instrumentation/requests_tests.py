import requests
from requests.exceptions import InvalidURL, MissingSchema
from urllib3_mock import Responses

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase

try:
    from requests.packages import urllib3  # noqa
    responses = Responses('requests.packages.urllib3')
except ImportError:
    responses = Responses('urllib3')


class InstrumentRequestsTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        elasticapm.instrumentation.control.instrument()
        responses.add('GET', '/', status=200, adding_headers={'Location': 'http://example.com/foo'})

    def test_requests_instrumentation(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            # NOTE: The `allow_redirects` argument has to be set to `False`,
            # because mocking is done a level deeper, and the mocked response
            # from the `HTTPAdapter` is about to be used to make further
            # requests to resolve redirects, which doesn't make sense for this
            # test case.
            requests.get('http://example.com', allow_redirects=False)
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']
        self.assertEqual('GET example.com', traces[0]['name'])
        self.assertEqual('http://example.com/', traces[0]['context']['url'])

    def test_requests_instrumentation_via_session(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            s = requests.Session()
            s.get('http://example.com', allow_redirects=False)
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']
        self.assertEqual('GET example.com', traces[0]['name'])
        self.assertEqual('http://example.com/', traces[0]['context']['url'])

    def test_requests_instrumentation_via_prepared_request(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            r = requests.Request('get', 'http://example.com')
            pr = r.prepare()
            s = requests.Session()
            s.send(pr, allow_redirects=False)
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']
        self.assertEqual('GET example.com', traces[0]['name'])
        self.assertEqual('http://example.com/', traces[0]['context']['url'])

    def test_requests_instrumentation_malformed_none(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            self.assertRaises(MissingSchema, requests.get, None)

    def test_requests_instrumentation_malformed_schema(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            self.assertRaises(MissingSchema, requests.get, '')

    def test_requests_instrumentation_malformed_path(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            self.assertRaises(InvalidURL, requests.get, 'http://')
