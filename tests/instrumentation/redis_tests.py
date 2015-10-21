from functools import partial

import mock
import redis
from redis.client import StrictRedis

import opbeat
import opbeat.instrumentation.control
from opbeat.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentRedisTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        opbeat.instrumentation.control.instrument()

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_pipeline(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            conn = redis.StrictRedis()
            pipeline = conn.pipeline()
            pipeline.rpush("mykey", "a", "b")
            pipeline.expire("mykey", 1000)
            pipeline.execute()
        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_pipeline',
                               'StrictPipeline.execute']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'MyView')

        self.assertEqual(traces[1]['signature'], 'test_pipeline')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'MyView')

        self.assertEqual(traces[2]['signature'], 'StrictPipeline.execute')
        self.assertEqual(traces[2]['kind'], 'cache.redis')
        self.assertEqual(traces[2]['transaction'], 'MyView')

        self.assertEqual(len(traces), 3)

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_rq_patches_redis(self, should_collect):
        should_collect.return_value = False

        # Let's go ahead and change how something important works
        conn = redis.StrictRedis()
        conn._pipeline = partial(StrictRedis.pipeline, conn)

        self.client.begin_transaction("transaction.test")
        with trace("test_pipeline", "test"):
            # conn = redis.StrictRedis()
            pipeline = conn._pipeline()
            pipeline.rpush("mykey", "a", "b")
            pipeline.expire("mykey", 1000)
            pipeline.execute()
        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_pipeline',
                               'StrictPipeline.execute']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'MyView')

        self.assertEqual(traces[1]['signature'], 'test_pipeline')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'MyView')

        self.assertEqual(traces[2]['signature'], 'StrictPipeline.execute')
        self.assertEqual(traces[2]['kind'], 'cache.redis')
        self.assertEqual(traces[2]['transaction'], 'MyView')

        self.assertEqual(len(traces), 3)

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_redis_client(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        with trace("test_redis_client", "test"):
            conn = redis.StrictRedis()
            conn.rpush("mykey", "a", "b")
            conn.expire("mykey", 1000)
        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_redis_client',
                               'RPUSH', 'EXPIRE']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'MyView')

        self.assertEqual(traces[1]['signature'], 'test_redis_client')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'MyView')

        self.assertEqual(traces[2]['signature'], 'RPUSH')
        self.assertEqual(traces[2]['kind'], 'cache.redis')
        self.assertEqual(traces[2]['transaction'], 'MyView')

        self.assertEqual(traces[3]['signature'], 'EXPIRE')
        self.assertEqual(traces[3]['kind'], 'cache.redis')
        self.assertEqual(traces[3]['transaction'], 'MyView')

        self.assertEqual(len(traces), 4)
