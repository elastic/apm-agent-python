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

import elasticapm

redis = pytest.importorskip("redis.asyncio")  # isort:skip

import os

import pytest_asyncio

from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span

pytestmark = [pytest.mark.asyncio, pytest.mark.redis]

if "REDIS_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping redis tests, no REDIS_HOST environment variable set"))


@pytest_asyncio.fixture()
async def redis_async_conn():
    _host = os.environ["REDIS_HOST"]
    _port = os.environ.get("REDIS_PORT", 6379)
    conn = await redis.Redis.from_url(f"redis://{_host}:{_port}")

    yield conn

    await conn.close(close_connection_pool=True)


@pytest.mark.integrationtest
async def test_ping(instrument, elasticapm_client, redis_async_conn):
    # The PING command is sent as a byte string, so this tests if we can handle
    # the command both as a str and as a bytes. See #1307
    elasticapm_client.begin_transaction("transaction.test")
    await redis_async_conn.ping()
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["name"] == "PING"
    assert span["duration"] > 0.2  # sanity test to ensure we measure the actual call


@pytest.mark.integrationtest
async def test_pipeline(instrument, elasticapm_client, redis_async_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_pipeline", "test"):
        pipeline = redis_async_conn.pipeline()
        pipeline.rpush("mykey", "a", "b")
        pipeline.expire("mykey", 1000)
        await pipeline.execute()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] == "Pipeline.execute"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "", "resource": "redis", "type": ""},
    }
    assert spans[0]["duration"] > 0.2  # sanity test to ensure we measure the actual call

    assert spans[1]["name"] == "test_pipeline"
    assert spans[1]["type"] == "test"

    assert len(spans) == 2


@pytest.mark.integrationtest
async def test_redis_client(instrument, elasticapm_client, redis_async_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_redis_client", "test"):
        await redis_async_conn.rpush("mykey", "a", "b")
        await redis_async_conn.expire("mykey", 1000)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    spans = sorted(spans, key=lambda x: x["name"])

    assert {t["name"] for t in spans} == {"test_redis_client", "RPUSH", "EXPIRE"}

    assert spans[0]["name"] == "EXPIRE"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "", "resource": "redis", "type": ""},
    }
    assert spans[0]["duration"] > 0.2  # sanity test to ensure we measure the actual call

    assert spans[1]["name"] == "RPUSH"
    assert spans[1]["type"] == "db"
    assert spans[1]["subtype"] == "redis"
    assert spans[1]["action"] == "query"
    assert spans[1]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "", "resource": "redis", "type": ""},
    }
    assert spans[1]["duration"] > 0.2  # sanity test to ensure we measure the actual call

    assert spans[2]["name"] == "test_redis_client"
    assert spans[2]["type"] == "test"

    assert len(spans) == 3


@pytest.mark.integrationtest
async def test_publish_subscribe_async(instrument, elasticapm_client, redis_async_conn):
    elasticapm_client.begin_transaction("transaction.test")
    pubsub = redis_async_conn.pubsub()
    with capture_span("test_publish_subscribe", "test"):
        # publish
        await redis_async_conn.publish("mykey", "a")

        # subscribe
        await pubsub.subscribe("mykey")

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_publish_subscribe", "PUBLISH", "SUBSCRIBE"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "PUBLISH"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "redis"
    assert spans[0]["action"] == "query"
    assert spans[0]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "", "resource": "redis", "type": ""},
    }
    assert spans[0]["duration"] > 0.2  # sanity test to ensure we measure the actual call

    assert spans[1]["name"] == "SUBSCRIBE"
    assert spans[1]["type"] == "db"
    assert spans[1]["subtype"] == "redis"
    assert spans[1]["action"] == "query"
    assert spans[1]["context"]["destination"] == {
        "address": os.environ.get("REDIS_HOST", "localhost"),
        "port": int(os.environ.get("REDIS_PORT", 6379)),
        "service": {"name": "", "resource": "redis", "type": ""},
    }
    assert spans[1]["duration"] > 0.2  # sanity test to ensure we measure the actual call

    assert spans[2]["name"] == "test_publish_subscribe"
    assert spans[2]["type"] == "test"

    assert len(spans) == 3


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        pytest.param({"transaction_max_spans": 1}),
    ],
    indirect=True,
)
@pytest.mark.integrationtest
async def test_dropped(instrument, elasticapm_client, redis_async_conn):
    # Test that our instrumentation doesn't blow up for dropped spans
    elasticapm_client.begin_transaction("transaction.test")
    async with elasticapm.async_capture_span("bla"):
        pass
    await redis_async_conn.ping()
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["name"] == "bla"
