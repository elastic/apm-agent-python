# isort:skip

import os

import pytest

from elasticapm.traces import capture_span

pylibmc = pytest.importorskip("pylibmc")

pytestmark = pytest.mark.pylibmc


@pytest.mark.integrationtest
def test_pylibmc(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_memcached", "test"):
        host = os.environ.get("MEMCACHED_HOST", "localhost")
        conn = pylibmc.Client([host + ":11211"])
        conn.set("mykey", "a")
        assert "a" == conn.get("mykey")
        assert {"mykey": "a"} == conn.get_multi(["mykey", "myotherkey"])
    elasticapm_client.end_transaction("BillingView")

    transactions = elasticapm_client.transaction_store.get_all()
    spans = transactions[0]["spans"]

    expected_signatures = {"test_memcached", "Client.set", "Client.get", "Client.get_multi"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "Client.set"
    assert spans[0]["type"] == "cache.memcached"
    assert spans[0]["parent"] == 0

    assert spans[1]["name"] == "Client.get"
    assert spans[1]["type"] == "cache.memcached"
    assert spans[1]["parent"] == 0

    assert spans[2]["name"] == "Client.get_multi"
    assert spans[2]["type"] == "cache.memcached"
    assert spans[2]["parent"] == 0

    assert spans[3]["name"] == "test_memcached"
    assert spans[3]["type"] == "test"

    assert len(spans) == 4
