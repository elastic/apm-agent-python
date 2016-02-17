import mock
import requests
from requests.exceptions import InvalidURL, MissingSchema

import opbeat
import opbeat.instrumentation.control
from opbeat.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentRequestsTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        opbeat.instrumentation.control.instrument()

    @mock.patch("requests.sessions.Session.send")
    def test_requests_instrumentation(self, _):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            requests.get('http://example.com')
        self.client.end_transaction("MyView")

        _, traces = self.client.instrumentation_store.get_all()
        self.assertIn('GET example.com', map(lambda x: x['signature'], traces))

    @mock.patch("requests.sessions.Session.send")
    def test_requests_instrumentation_via_session(self, _):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            s = requests.Session()
            s.get('http://example.com')
        self.client.end_transaction("MyView")

        _, traces = self.client.instrumentation_store.get_all()
        self.assertIn('GET example.com', map(lambda x: x['signature'], traces))

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
