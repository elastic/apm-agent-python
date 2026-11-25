#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import asyncio
import os
from unittest.mock import MagicMock

import pytest
import pytest_asyncio

import elasticapm
from elasticapm.conf.constants import OUTCOME, SPAN, TRACEPARENT_BINARY_HEADER_NAME, TRANSACTION
from elasticapm.instrumentation.packages.asyncio.aiokafka import _inject_trace_parent_into_send_arguments
from elasticapm.utils.disttracing import TraceParent

aiokafka = pytest.importorskip("aiokafka")
aiokafka_admin = pytest.importorskip("aiokafka.admin")

pytestmark = [pytest.mark.aiokafka]

KAFKA_HOST = os.environ.get("KAFKA_HOST")
if not KAFKA_HOST:
    pytestmark.append(pytest.mark.skip("Skipping aiokafka tests, no KAFKA_HOST environment variable set"))


@pytest_asyncio.fixture(scope="function")
async def topics():
    topics = ["test", "foo", "bar"]
    admin_client = aiokafka_admin.AIOKafkaAdminClient(bootstrap_servers=[f"{KAFKA_HOST}:9092"])

    await admin_client.start()
    await admin_client.create_topics(
        [aiokafka_admin.NewTopic(name, num_partitions=1, replication_factor=1) for name in topics]
    )
    try:
        yield topics
    finally:
        await admin_client.delete_topics(topics)


@pytest_asyncio.fixture()
async def producer():
    producer = aiokafka.AIOKafkaProducer(bootstrap_servers=f"{KAFKA_HOST}:9092")
    await producer.start()
    await producer.client.bootstrap()
    try:
        yield producer
    finally:
        await producer.stop()


@pytest_asyncio.fixture()
async def consumer(topics):
    consumer = aiokafka.AIOKafkaConsumer(bootstrap_servers=f"{KAFKA_HOST}:9092")
    consumer.subscribe(topics=topics)
    await consumer.start()

    async def consumer_close_later():
        await asyncio.sleep(1.0)
        await consumer.stop()

    task = asyncio.create_task(consumer_close_later())
    try:
        yield consumer
    finally:
        await task


@pytest.mark.asyncio
async def test_aiokafka_produce(instrument, elasticapm_client, producer, topics):
    elasticapm_client.begin_transaction("test")
    await producer.send("test", key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.events[SPAN][0]
    assert span["name"] == "Kafka SEND to test"
    assert span["context"]["message"]["queue"]["name"] == "test"
    assert span["context"]["destination"]["port"] == 9092
    assert span["context"]["destination"]["service"]["name"] == "kafka"
    assert span["context"]["destination"]["service"]["resource"] == "kafka/test"
    assert span["context"]["destination"]["service"]["type"] == "messaging"


@pytest.mark.asyncio
async def test_aiokafka_produce_ignore_topic(instrument, elasticapm_client, producer, topics):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")
    elasticapm_client.begin_transaction("test")
    await producer.send(topic="foo", key=b"foo", value=b"bar")
    await producer.send("bar", key=b"foo", value=b"bar")
    await producer.send("test", key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka SEND to test"


@pytest.mark.asyncio
async def test_aiokafka_consume(instrument, elasticapm_client, producer, consumer, topics):
    async def delayed_send():
        await asyncio.sleep(0.2)
        elasticapm_client.begin_transaction("foo")
        await producer.send("test", key=b"foo", value=b"bar")
        await producer.send("test", key=b"baz", value=b"bazzinga")
        elasticapm_client.end_transaction("foo")

    task = asyncio.create_task(delayed_send())
    async for item in consumer:
        with elasticapm.capture_span("foo"):
            pass
    await task
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    # the consumer transactions should have the same trace id as the transaction that triggered the messages
    assert transactions[0]["trace_id"] == transactions[1]["trace_id"] == transactions[2]["trace_id"]
    assert transactions[1]["name"] == "Kafka RECEIVE from test"
    assert transactions[1]["type"] == "messaging"
    assert transactions[1]["context"]["message"]["queue"]["name"] == "test"

    assert spans[2]["transaction_id"] == transactions[1]["id"]
    assert spans[3]["transaction_id"] == transactions[2]["id"]


@pytest.mark.asyncio
async def test_aiokafka_consume_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    async def delayed_send():
        await asyncio.sleep(0.2)
        elasticapm_client.begin_transaction("foo")
        await producer.send("test", key=b"foo", value=b"bar")
        await producer.send("test", key=b"baz", value=b"bazzinga")
        elasticapm_client.end_transaction("foo")

    task = asyncio.create_task(delayed_send())
    transaction = elasticapm_client.begin_transaction("foo")
    async for item in consumer:
        pass
    await task
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 2
    external_spans = elasticapm_client.spans_for_transaction(transactions[0])
    spans = elasticapm_client.spans_for_transaction(transactions[1])
    assert len(external_spans) == 2
    assert len(spans) == 3
    assert spans[0]["links"][0]["trace_id"] == external_spans[0]["trace_id"]
    assert spans[1]["links"][0]["trace_id"] == external_spans[1]["trace_id"]
    # It records the last span that was awaiting when stopping the consumer as a failure.
    assert spans[2]["outcome"] == OUTCOME.FAILURE
    assert "links" not in spans[2]


@pytest.mark.asyncio
async def test_aiokafka_consumer_ignore_topic(instrument, elasticapm_client, producer, consumer, topics):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")

    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send(topic="foo", key=b"foo", value=b"bar")
        await producer.send("bar", key=b"foo", value=b"bar")
        await producer.send("test", key=b"foo", value=b"bar")

    task = asyncio.create_task(delayed_send())
    async for item in consumer:
        with elasticapm.capture_span("test"):
            assert item
    await task
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 1
    assert transactions[0]["name"] == "Kafka RECEIVE from test"


@pytest.mark.asyncio
async def test_aiokafka_consumer_ignore_topic_ongoing_transaction(
    instrument, elasticapm_client, producer, consumer, topics
):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")

    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send(topic="foo", key=b"foo", value=b"bar")
        await producer.send("bar", key=b"foo", value=b"bar")
        await producer.send("test", key=b"foo", value=b"bar")

    task = asyncio.create_task(delayed_send())
    transaction = elasticapm_client.begin_transaction("foo")
    async for item in consumer:
        pass
    await task
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 2
    assert spans[0]["name"] == "Kafka RECEIVE from test"
    # It records the last span that was awaiting when stopping the consumer as a failure.
    assert spans[1]["outcome"] == OUTCOME.FAILURE
    assert spans[1]["name"] == "Kafka RECEIVE"


@pytest.mark.asyncio
async def test_aiokafka_getmany_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send("test", key=b"foo", value=b"bar")
        await producer.send("test", key=b"baz", value=b"bazzinga")

    task = asyncio.create_task(delayed_send())
    transaction = elasticapm_client.begin_transaction("foo")
    results = await consumer.getmany(timeout_ms=1000)
    await task
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka RECEIVE from test"


@pytest.mark.asyncio
async def test_aiokafka_no_client(instrument, producer, consumer, topics):
    assert elasticapm.get_client() is None
    # the following code shouldn't trigger any errors
    await producer.send_and_wait("test", key=b"foo", value=b"bar")
    async for item in consumer:
        pass


@pytest.mark.asyncio
async def test_aiokafka_send_unsampled_transaction(instrument, elasticapm_client, producer, topics):
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    await producer.send("test", key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


@pytest.mark.asyncio
async def test_aiokafka_getmany_unsampled_transaction(instrument, elasticapm_client, consumer, topics):
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    await consumer.getmany(timeout_ms=50)
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


@pytest.mark.asyncio
async def test_aiokafka_consumer_unsampled_transaction_handles_stop_iteration(
    instrument, elasticapm_client, producer, consumer, topics
):
    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send("test", key=b"foo", value=b"bar")

    task = asyncio.create_task(delayed_send())
    transaction = elasticapm_client.begin_transaction("foo")
    transaction.is_sampled = False
    async for item in consumer:
        pass
    await task
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


@pytest.mark.asyncio
async def test_aiokafka_getmany_multiple_topics(instrument, elasticapm_client, producer, consumer, topics):
    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send("foo", key=b"foo", value=b"bar")
        await producer.send("bar", key=b"foo", value=b"bar")
        await producer.send("test", key=b"baz", value=b"bazzinga")

    task = asyncio.create_task(delayed_send())
    await asyncio.sleep(0.5)  # Wait a while so it can get all messages at once.

    elasticapm_client.config.update("1", ignore_message_queues="bar")
    elasticapm_client.begin_transaction("foo")
    results = await consumer.getmany()
    await task
    elasticapm_client.end_transaction()

    assert len(results) == 3
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka RECEIVE from foo, test"


@pytest.mark.asyncio
async def test_aiokafka_send_batch(instrument, elasticapm_client, producer, consumer, topics):
    async def delayed_send():
        await asyncio.sleep(0.2)

        batch = producer.create_batch()
        batch.append(key=b"foo", value=b"bar", timestamp=None)
        batch.append(key=b"baz", value=b"bazzinga", timestamp=None)
        partitions = await producer.partitions_for("test")

        elasticapm_client.begin_transaction("send")
        await producer.send_batch(batch, "test", partition=partitions.pop())
        elasticapm_client.end_transaction()

    task = asyncio.create_task(delayed_send())
    elasticapm_client.begin_transaction("recv")
    async for _ in consumer:
        pass
    await task
    elasticapm_client.end_transaction()
    await task

    tran_send, tran_recv = elasticapm_client.events[TRANSACTION]
    spans_send = elasticapm_client.spans_for_transaction(tran_send)
    spans_recv = elasticapm_client.spans_for_transaction(tran_recv)

    assert len(spans_send) == 1
    assert len(spans_recv) == 3
    assert "links" not in spans_recv[0]
    assert "links" not in spans_recv[1]
    # It records the last span that was awaiting when stopping the consumer as a failure.
    assert spans_recv[2]["outcome"] == OUTCOME.FAILURE
    assert "links" not in spans_recv[2]
    assert all(spans_send[0]["trace_id"] != span_recv["trace_id"] for span_recv in spans_recv)


@pytest.mark.asyncio
async def test_aiokafka_consumer_non_recording_transaction(instrument, elasticapm_client, producer, consumer, topics):
    elasticapm_client.config.update("1", recording=False)

    async def delayed_send():
        await asyncio.sleep(0.2)
        await producer.send("test", key=b"foo", value=b"bar")

    task = asyncio.create_task(delayed_send())
    async for item in consumer:
        pass
    await task
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 0


def test_aiokafka_inject_trace_parent_into_send_arguments():
    trace_parent = TraceParent.from_string("00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01")
    assert trace_parent
    traceparent_header = (TRACEPARENT_BINARY_HEADER_NAME, trace_parent.to_binary())
    headers_list = [("header_name", "header_value")]
    headers_list_but_malformed = [tuple()]
    headers_list_with_other_traceparent = [(TRACEPARENT_BINARY_HEADER_NAME, ...)]
    headers_none = None
    batch = aiokafka.AIOKafkaProducer.create_batch(self=MagicMock())

    def func(*args, **kwargs):
        mutable_args = list(args)
        _inject_trace_parent_into_send_arguments(mutable_args, kwargs, trace_parent)
        return mutable_args, kwargs

    # send(topic, value=None, key=None, partition=None, timestamp_ms=None, headers=None)
    args, kwargs = func("topic", key=..., value=...)
    assert traceparent_header in kwargs["headers"]

    args, kwargs = func("topic", key=..., value=..., headers=headers_list)
    assert traceparent_header in kwargs["headers"]
    assert len(kwargs["headers"]) == 2  # The traceparent header should be appended

    args, kwargs = func("topic", key=..., value=..., headers=headers_list_but_malformed)
    assert traceparent_header in kwargs["headers"]
    assert len(kwargs["headers"]) == 2  # Injection should succeed despite malformed headers

    args, kwargs = func("topic", key=..., value=..., headers=headers_list_with_other_traceparent)
    assert traceparent_header in kwargs["headers"]
    assert len(kwargs["headers"]) == 1  # The traceparent header should be overwritten

    args, kwargs = func("topic", key=..., value=..., headers=headers_none)
    assert traceparent_header in kwargs["headers"]

    args, kwargs = func("topic", "value", "key", "partition", "timestamp_ms")
    assert traceparent_header in kwargs["headers"]

    args, kwargs = func("topic", "partition", headers_none, key=..., value=..., timestamp_ms=...)
    assert traceparent_header in args[2]

    args, kwargs = func("topic", "value", "key", "partition", "timestamp_ms", headers_none)
    assert traceparent_header in args[5]

    args, kwargs = func("topic", "value", "key", "partition", "timestamp_ms", headers_list)
    assert traceparent_header in args[5]

    with pytest.raises(TypeError, match=r"\bMutableSequence\b"):
        args, kwargs = func("topic", "value", headers=tuple())

    with pytest.raises(TypeError, match=r"\bMutableSequence\b"):
        args, kwargs = func("topic", "value", headers=dict())

    # send_batch(batch, topic, *, partition)
    args, kwargs = func(batch, "topic", partition=...)
    assert "headers" not in kwargs
    assert len(args) == 2

    args, kwargs = func("topic", partition=..., batch=...)
    assert "headers" not in kwargs
    assert len(args) == 1

    args, kwargs = func(topic=..., partition=..., batch=...)
    assert "headers" not in kwargs
    assert len(args) == 0
