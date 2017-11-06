import os

import memcache
import pytest

from elasticapm.traces import trace


@pytest.mark.integrationtest
def test_memcached(elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with trace("test_memcached", "test"):
        host = os.environ.get('MEMCACHED_HOST', 'localhost')
        conn = memcache.Client([host + ':11211'], debug=0)
        conn.set("mykey", "a")
        assert "a" == conn.get("mykey")
        assert {"mykey": "a"} == conn.get_multi(["mykey", "myotherkey"])
    elasticapm_client.end_transaction("BillingView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'test_memcached',
                           'Client.set', 'Client.get',
                           'Client.get_multi'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'Client.set'
    assert traces[0]['type'] == 'cache.memcached'
    assert traces[0]['parent'] == 0

    assert traces[1]['name'] == 'Client.get'
    assert traces[1]['type'] == 'cache.memcached'
    assert traces[1]['parent'] == 0

    assert traces[2]['name'] == 'Client.get_multi'
    assert traces[2]['type'] == 'cache.memcached'
    assert traces[2]['parent'] == 0

    assert traces[3]['name'] == 'test_memcached'
    assert traces[3]['type'] == 'test'

    assert len(traces) == 4
