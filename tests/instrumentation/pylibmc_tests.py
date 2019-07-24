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

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_memcached", "Client.set", "Client.get", "Client.get_multi"}

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

    assert spans[2]["name"] == "Client.get_multi"
    assert spans[2]["type"] == "cache"
    assert spans[2]["subtype"] == "memcached"
    assert spans[2]["action"] == "query"
    assert spans[2]["parent_id"] == spans[3]["id"]

    assert spans[3]["name"] == "test_memcached"
    assert spans[3]["type"] == "test"

    assert len(spans) == 4
