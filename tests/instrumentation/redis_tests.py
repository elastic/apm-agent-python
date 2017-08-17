from functools import partial

import mock
import pytest
import redis
from redis.client import StrictRedis

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


@pytest.mark.integrationtest
class InstrumentRedisTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        elasticapm.instrumentation.control.instrument()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
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

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'test_pipeline',
                               'StrictPipeline.execute']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], 'StrictPipeline.execute')
        self.assertEqual(traces[0]['type'], 'cache.redis')

        self.assertEqual(traces[1]['name'], 'test_pipeline')
        self.assertEqual(traces[1]['type'], 'test')

        self.assertEqual(traces[2]['name'], 'transaction')
        self.assertEqual(traces[2]['type'], 'transaction')

        self.assertEqual(len(traces), 3)

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
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

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'test_pipeline',
                               'StrictPipeline.execute']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], 'StrictPipeline.execute')
        self.assertEqual(traces[0]['type'], 'cache.redis')

        self.assertEqual(traces[1]['name'], 'test_pipeline')
        self.assertEqual(traces[1]['type'], 'test')

        self.assertEqual(traces[2]['name'], 'transaction')
        self.assertEqual(traces[2]['type'], 'transaction')

        self.assertEqual(len(traces), 3)

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_redis_client(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        with trace("test_redis_client", "test"):
            conn = redis.StrictRedis()
            conn.rpush("mykey", "a", "b")
            conn.expire("mykey", 1000)
        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'test_redis_client',
                               'RPUSH', 'EXPIRE']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], 'RPUSH')
        self.assertEqual(traces[0]['type'], 'cache.redis')

        self.assertEqual(traces[1]['name'], 'EXPIRE')
        self.assertEqual(traces[1]['type'], 'cache.redis')

        self.assertEqual(traces[2]['name'], 'test_redis_client')
        self.assertEqual(traces[2]['type'], 'test')

        self.assertEqual(traces[3]['name'], 'transaction')
        self.assertEqual(traces[3]['type'], 'transaction')

        self.assertEqual(len(traces), 4)
