import os
from functools import partial

import mock
import pytest
import redis
from redis.client import StrictRedis

from elasticapm.traces import trace


@pytest.fixture()
def redis_conn():
    conn = redis.StrictRedis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=os.environ.get('REDIS_PORT', 6379),

    )
    yield conn
    del conn


@pytest.mark.integrationtest
def test_pipeline(elasticapm_client, redis_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with trace("test_pipeline", "test"):
        pipeline = redis_conn.pipeline()
        pipeline.rpush("mykey", "a", "b")
        pipeline.expire("mykey", 1000)
        pipeline.execute()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'test_pipeline', 'StrictPipeline.execute'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'StrictPipeline.execute'
    assert traces[0]['type'] == 'cache.redis'

    assert traces[1]['name'] == 'test_pipeline'
    assert traces[1]['type'] == 'test'

    assert len(traces) == 2


@pytest.mark.integrationtest
def test_rq_patches_redis(elasticapm_client, redis_conn):
    # Let's go ahead and change how something important works
    redis_conn._pipeline = partial(StrictRedis.pipeline, redis_conn)

    elasticapm_client.begin_transaction("transaction.test")
    with trace("test_pipeline", "test"):
        # conn = redis.StrictRedis()
        pipeline = redis_conn._pipeline()
        pipeline.rpush("mykey", "a", "b")
        pipeline.expire("mykey", 1000)
        pipeline.execute()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'test_pipeline', 'StrictPipeline.execute'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'StrictPipeline.execute'
    assert traces[0]['type'] == 'cache.redis'

    assert traces[1]['name'] == 'test_pipeline'
    assert traces[1]['type'] == 'test'

    assert len(traces) == 2


@pytest.mark.integrationtest
def test_redis_client(elasticapm_client, redis_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with trace("test_redis_client", "test"):
        redis_conn.rpush("mykey", "a", "b")
        redis_conn.expire("mykey", 1000)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'test_redis_client', 'RPUSH', 'EXPIRE'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'RPUSH'
    assert traces[0]['type'] == 'cache.redis'

    assert traces[1]['name'] == 'EXPIRE'
    assert traces[1]['type'] == 'cache.redis'

    assert traces[2]['name'] == 'test_redis_client'
    assert traces[2]['type'] == 'test'

    assert len(traces) == 3
