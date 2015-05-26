from django.test import TestCase
import urllib3
from opbeat.contrib.django.models import get_client


class InstrumentRedisTest(TestCase):
    def setUp(self):
        self.client = get_client()
        # self.client.request_store = RequestsStore(lambda: [], 99999)

    def test_pipeline(self):
        self.client.begin_transaction()
        with self.client.capture_trace("test_pipeline", "test"):
            pool = urllib3.PoolManager(timeout=0.1)
            r = pool.request('GET', 'http://example.com/', )

        self.client.end_transaction(None, "test")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_pipeline', 'GET example.com']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(len(traces), 3)

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'test')

        self.assertEqual(traces[1]['signature'], 'test_pipeline')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'test')

        self.assertEqual(traces[2]['signature'], 'GET example.com')
        self.assertEqual(traces[2]['kind'], 'ext.http.urllib3')
        self.assertEqual(traces[2]['transaction'], 'test')

        self.assertEqual(traces[2]['extra']['url'], 'http://example.com/')





