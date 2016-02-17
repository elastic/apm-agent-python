import requests
from requests.exceptions import InvalidURL, MissingSchema
from urllib3.exceptions import ConnectionError

import opbeat
import opbeat.instrumentation.control
from opbeat.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentRequestsTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        opbeat.instrumentation.control.instrument()

    def test_requests_instrumentation(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            try:
                requests.get('http://example.com')
            except ConnectionError:
                pass
        self.client.end_transaction("MyView")

        _, traces = self.client.instrumentation_store.get_all()
        self.assertIn('GET example.com', map(lambda x: x['signature'], traces))

    def test_requests_instrumentation_via_session(self):
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            s = requests.Session()
            try:
                s.get('http://example.com')
            except ConnectionError:
                pass
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


