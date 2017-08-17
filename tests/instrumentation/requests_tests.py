import mock
import requests
from requests.exceptions import InvalidURL, MissingSchema

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentRequestsTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        elasticapm.instrumentation.control.instrument()

    @mock.patch("requests.adapters.HTTPAdapter.send")
    def test_requests_instrumentation(self, mock_send):
        mock_send.return_value = mock.Mock(
            url='http://example.com',
            history=[],
            headers={'location': ''},
        )
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

    @mock.patch("requests.adapters.HTTPAdapter.send")
    def test_requests_instrumentation_via_session(self, mock_send):
        mock_send.return_value = mock.Mock(
            url='http://example.com',
            history=[],
            headers={'location': ''},
        )
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            s = requests.Session()
            s.get('http://example.com', allow_redirects=False)
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']
        self.assertEqual('GET example.com', traces[0]['name'])
        self.assertEqual('http://example.com/', traces[0]['context']['url'])

    @mock.patch("requests.adapters.HTTPAdapter.send")
    def test_requests_instrumentation_via_prepared_request(self, mock_send):
        mock_send.return_value = mock.Mock(
            url='http://example.com',
            history=[],
            headers={'location': ''},
        )
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
