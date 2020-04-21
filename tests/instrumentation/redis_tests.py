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

import pytest  # isort:skip

redis = pytest.importorskip("redis")  # isort:skip

import os
from functools import partial

from redis import UnixDomainSocketConnection
from redis.client import StrictRedis

from elasticapm.conf.constants import TRANSACTION
from elasticapm.instrumentation.packages.redis import get_destination_info
from elasticapm.traces import capture_span

pytestmark = [pytest.mark.redis]

if "REDIS_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping redis tests, no REDIS_HOST environment variable set"))


@pytest.fixture()
def redis_conn():
    conn = redis.StrictRedis(host=os.environ["REDIS_HOST"], port=os.environ.get("REDIS_PORT", 6379))
    yield conn
    del conn


@pytest.mark.integrationtest
def test_pipeline(instrument, elasticapm_client, redis_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_pipeline", "test"):
        pipeline = redis_conn.pipeline()
        pipeline.rpush("mykey", "a", "b")
        pipeline.expire("mykey", 1000)
        pipeline.execute()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] in ("StrictPipeline.execute", "Pipeline.execute")
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "redis", "resource": "redis", "type": "db"},
    }

    assert spans[1]["name"] == "test_pipeline"
    assert spans[1]["type"] == "test"

    assert len(spans) == 2


@pytest.mark.integrationtest
def test_rq_patches_redis(instrument, elasticapm_client, redis_conn):
    # Let's go ahead and change how something important works
    redis_conn._pipeline = partial(StrictRedis.pipeline, redis_conn)

    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_pipeline", "test"):
        # conn = redis.StrictRedis()
        pipeline = redis_conn._pipeline()
        pipeline.rpush("mykey", "a", "b")
        pipeline.expire("mykey", 1000)
        pipeline.execute()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] in ("StrictPipeline.execute", "Pipeline.execute")
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "redis", "resource": "redis", "type": "db"},
    }

    assert spans[1]["name"] == "test_pipeline"
    assert spans[1]["type"] == "test"

    assert len(spans) == 2


@pytest.mark.integrationtest
def test_redis_client(instrument, elasticapm_client, redis_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_redis_client", "test"):
        redis_conn.rpush("mykey", "a", "b")
        redis_conn.expire("mykey", 1000)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_redis_client", "RPUSH", "EXPIRE"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "RPUSH"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "redis", "resource": "redis", "type": "db"},
    }

    assert spans[1]["name"] == "EXPIRE"
    assert spans[1]["type"] == "db"
    assert spans[1]["subtype"] == "redis"
    assert spans[1]["action"] == "query"
    assert spans[1]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "redis", "resource": "redis", "type": "db"},
    }

    assert spans[2]["name"] == "test_redis_client"
    assert spans[2]["type"] == "test"

    assert len(spans) == 3


def test_unix_domain_socket_connection_destination_info():
    conn = UnixDomainSocketConnection("/some/path")
    destination_info = get_destination_info(conn)
    assert destination_info["port"] is None
    assert destination_info["address"] == "unix:///some/path"
