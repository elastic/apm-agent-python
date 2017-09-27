import os

import memcache
import mock

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentMemcachedTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        elasticapm.instrumentation.control.instrument()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_memcached(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")
        with trace("test_memcached", "test"):
            host = os.environ.get('MEMCACHED_HOST', 'localhost')
            conn = memcache.Client([host + ':11211'], debug=0)
            conn.set("mykey", "a")
            assert "a" == conn.get("mykey")
            assert {"mykey": "a"} == conn.get_multi(["mykey", "myotherkey"])
        self.client.end_transaction("BillingView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = {'test_memcached',
                               'Client.set', 'Client.get',
                               'Client.get_multi'}

        self.assertEqual({t['name'] for t in traces}, expected_signatures)

        self.assertEqual(traces[0]['name'], 'Client.set')
        self.assertEqual(traces[0]['type'], 'cache.memcached')
        self.assertEqual(traces[0]['parent'], 0)

        self.assertEqual(traces[1]['name'], 'Client.get')
        self.assertEqual(traces[1]['type'], 'cache.memcached')
        self.assertEqual(traces[1]['parent'], 0)

        self.assertEqual(traces[2]['name'], 'Client.get_multi')
        self.assertEqual(traces[2]['type'], 'cache.memcached')
        self.assertEqual(traces[2]['parent'], 0)

        self.assertEqual(traces[3]['name'], 'test_memcached')
        self.assertEqual(traces[3]['type'], 'test')

        self.assertEqual(len(traces), 4)
