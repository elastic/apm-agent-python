import os
from functools import partial

import pytest
import redis
from redis.client import StrictRedis

from elasticapm.traces import capture_span


@pytest.fixture()
def redis_conn():
    conn = redis.StrictRedis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=os.environ.get('REDIS_PORT', 6379),

    )
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

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']

    expected_signatures = {'test_pipeline', 'StrictPipeline.execute'}

    assert {t['name'] for t in spans} == expected_signatures

    assert spans[0]['name'] == 'StrictPipeline.execute'
    assert spans[0]['type'] == 'cache.redis'

    assert spans[1]['name'] == 'test_pipeline'
    assert spans[1]['type'] == 'test'

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

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']

    expected_signatures = {'test_pipeline', 'StrictPipeline.execute'}

    assert {t['name'] for t in spans} == expected_signatures

    assert spans[0]['name'] == 'StrictPipeline.execute'
    assert spans[0]['type'] == 'cache.redis'

    assert spans[1]['name'] == 'test_pipeline'
    assert spans[1]['type'] == 'test'

    assert len(spans) == 2


@pytest.mark.integrationtest
def test_redis_client(instrument, elasticapm_client, redis_conn):
    elasticapm_client.begin_transaction("transaction.test")
    with capture_span("test_redis_client", "test"):
        redis_conn.rpush("mykey", "a", "b")
        redis_conn.expire("mykey", 1000)
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']

    expected_signatures = {'test_redis_client', 'RPUSH', 'EXPIRE'}

    assert {t['name'] for t in spans} == expected_signatures

    assert spans[0]['name'] == 'RPUSH'
    assert spans[0]['type'] == 'cache.redis'

    assert spans[1]['name'] == 'EXPIRE'
    assert spans[1]['type'] == 'cache.redis'

    assert spans[2]['name'] == 'test_redis_client'
    assert spans[2]['type'] == 'test'

    assert len(spans) == 3
