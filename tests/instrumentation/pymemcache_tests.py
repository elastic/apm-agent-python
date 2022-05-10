#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os

import pytest

from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span

pymemcache = pytest.importorskip("pymemcache")  # isort:skip


pytestmark = [pytest.mark.pymemcache]


if "MEMCACHED_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping pymemcache tests, no MEMCACHED_HOST environment variable set"))


@pytest.fixture()
def mc_conn(request):
    params = getattr(request, "param", {})
    client_class = params.get("client_class", pymemcache.client.base.Client)
    host = os.environ.get("MEMCACHED_HOST", "localhost")
    port = int(os.environ.get("MEMCACHED_PORT", "11211"))
    client = client_class((host, port))
    yield client
    client.flush_all()


@pytest.mark.integrationtest
def test_pymemcache_client(instrument, elasticapm_client, mc_conn):
    elasticapm_client.begin_transaction("transaction.test")
    host = os.environ.get("MEMCACHED_HOST", "localhost")
    with capture_span("test_pymemcache", "test"):
        mc_conn.set("mykey", "a")
        assert b"a" == mc_conn.get("mykey")
        assert {"mykey": b"a"} == mc_conn.get_many(["mykey", "myotherkey"])
    elasticapm_client.end_transaction("BillingView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_pymemcache", "Client.set", "Client.get", "Client.get_many"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "Client.set"
    assert spans[0]["type"] == "cache"
    assert spans[0]["subtype"] == "memcached"
    assert spans[0]["action"] == "query"
    assert spans[0]["parent_id"] == spans[3]["id"]

    assert spans[1]["name"] == "Client.get"
    assert spans[1]["type"] == "cache"
    assert spans[1]["subtype"] == "memcached"
    assert spans[1]["action"] == "query"
    assert spans[1]["parent_id"] == spans[3]["id"]
    assert spans[1]["context"]["destination"] == {
        "address": host,
        "port": 11211,
        "service": {"name": "", "resource": "memcached", "type": ""},
    }

    assert spans[2]["name"] == "Client.get_many"
    assert spans[2]["type"] == "cache"
    assert spans[2]["subtype"] == "memcached"
    assert spans[2]["action"] == "query"
    assert spans[2]["parent_id"] == spans[3]["id"]

    assert spans[3]["name"] == "test_pymemcache"
    assert spans[3]["type"] == "test"

    assert len(spans) == 4


@pytest.mark.parametrize("mc_conn", [{"client_class": pymemcache.client.base.PooledClient}], indirect=True)
@pytest.mark.integrationtest
def test_pymemcache_pooled_client(instrument, elasticapm_client, mc_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_pymemcache", "test"):
        mc_conn.set("mykey", "a")
        assert b"a" == mc_conn.get("mykey")
        assert {"mykey": b"a"} == mc_conn.get_many(["mykey", "myotherkey"])
    elasticapm_client.end_transaction("BillingView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {
        "test_pymemcache",
        "PooledClient.set",
        "PooledClient.get",
        "PooledClient.get_many",
    }

    assert {t["name"] for t in spans} == expected_signatures

    assert len(spans) == 4


@pytest.mark.integrationtest
def test_pymemcache_hash_client(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    host = os.environ.get("MEMCACHED_HOST", "localhost")
    with capture_span("test_pymemcache", "test"):
        conn = pymemcache.client.hash.HashClient([(host, 11211)])  # can't use mc_conn here due to different init
        conn.set("mykey", "a")
        assert b"a" == conn.get("mykey")
        assert {"mykey": b"a"} == conn.get_many(["mykey", "myotherkey"])
    elasticapm_client.end_transaction("BillingView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {
        "test_pymemcache",
        "HashClient.set",
        "HashClient.get",
        "HashClient.get_many",
    }

    assert {t["name"] for t in spans} == expected_signatures

    assert len(spans) == 4


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {
            "span_compression_enabled": True,
            "span_compression_same_kind_max_duration": "5ms",
            "span_compression_exact_match_max_duration": "5ms",
        }
    ],
    indirect=True,
)
@pytest.mark.integrationtest
def test_memcache_span_compression(instrument, elasticapm_client, mc_conn):
    elasticapm_client.begin_transaction("transaction.test")
    for i in range(5):
        mc_conn.set(str(i), i)
    elasticapm_client.end_transaction("test")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 1
