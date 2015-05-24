from django.test import TestCase
import redis
from opbeat.contrib.django.models import get_client


class InstrumentRedisTest(TestCase):
    def setUp(self):
        self.client = get_client()
        # self.client.request_store = RequestsStore(lambda: [], 99999)

    def test_pipeline(self):
        self.client.begin_transaction()
        with self.client.capture_trace("test_pipeline", "test"):
            conn = redis.StrictRedis()
            pipeline = conn.pipeline()
            pipeline.rpush("mykey", "a", "b")
            pipeline.expire("mykey", 1000)
            pipeline.execute()
        self.client.end_transaction(None, "test")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_pipeline',
                               'StrictRedis.pipeline', 'StrictPipeline.rpush',
                               'StrictPipeline.expire',
                               'StrictPipeline.execute']

        self.assertEqual(set([t['signature'] for t in traces]),
                             set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'test')

        self.assertEqual(traces[1]['signature'], 'test_pipeline')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'test')

        self.assertEqual(traces[2]['signature'], 'StrictRedis.pipeline')
        self.assertEqual(traces[2]['kind'], 'cache.redis')
        self.assertEqual(traces[2]['transaction'], 'test')

        self.assertEqual(len(traces), 6)



