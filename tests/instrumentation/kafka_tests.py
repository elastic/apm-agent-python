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

import os
import time
import uuid
import warnings

import pytest

import elasticapm
from elasticapm.conf.constants import SPAN, TRANSACTION

kafka = pytest.importorskip("kafka")

from kafka import KafkaConsumer, KafkaProducer, TopicPartition, errors as kafka_errors
from kafka.admin import KafkaAdminClient, NewTopic

pytestmark = [pytest.mark.kafka]

KAFKA_HOST = os.environ.get("KAFKA_HOST")
if not KAFKA_HOST:
    pytestmark.append(pytest.mark.skip("Skipping kafka tests, no KAFKA_HOST environment variable set"))

KAFKA_BOOTSTRAP_SERVER = f"{KAFKA_HOST}:9092"
KAFKA_OPERATION_TIMEOUT_MS = 3000
KAFKA_READINESS_TIMEOUT_SECONDS = 15
KAFKA_CONSUME_TIMEOUT_MS = 1000
KAFKA_READY_POLL_TIMEOUT_MS = 100
KAFKA_POLL_INTERVAL_SECONDS = 0.1


def _format_topic_partition(topic_partition):
    return f"{topic_partition.topic}[{topic_partition.partition}]"


def _format_kafka_error(error_code):
    error = kafka_errors.for_code(error_code)
    return f"{error.__name__}({error_code})"


def _raise_kafka_timeout(kind, names, details):
    raise AssertionError(f"Timed out waiting for Kafka {kind} for {sorted(names)}: {details}")


def _create_topics(admin_client, names, monotonic=time.monotonic, sleep=time.sleep):
    deadline = monotonic() + KAFKA_READINESS_TIMEOUT_SECONDS
    topics = [NewTopic(name, num_partitions=1, replication_factor=1) for name in names]
    last_error = None
    while True:
        try:
            admin_client.create_topics(topics, timeout_ms=KAFKA_OPERATION_TIMEOUT_MS)
            return
        except kafka_errors.TopicAlreadyExistsError:
            return
        except kafka_errors.KafkaError as exc:
            last_error = repr(exc)
            if not exc.retriable:
                raise AssertionError(f"Failed to create Kafka topics {sorted(names)}: {last_error}") from exc
        if monotonic() >= deadline:
            _raise_kafka_timeout("topic creation", names, f"last error={last_error}")
        sleep(KAFKA_POLL_INTERVAL_SECONDS)


def _wait_for_topics_ready(admin_client, names, monotonic=time.monotonic, sleep=time.sleep):
    deadline = monotonic() + KAFKA_READINESS_TIMEOUT_SECONDS
    last_error = None
    while True:
        try:
            descriptions = admin_client.describe_topics(names)
        except kafka_errors.KafkaError as exc:
            last_error = repr(exc)
            if not exc.retriable:
                raise AssertionError(f"Failed to describe Kafka topics {sorted(names)}: {last_error}") from exc
        else:
            descriptions_by_name = {description["topic"]: description for description in descriptions}
            missing_topics = sorted(name for name in names if name not in descriptions_by_name)
            missing_partitions = []
            leaderless_partitions = []
            retryable_errors = []
            fatal_errors = []

            for name in names:
                description = descriptions_by_name.get(name)
                if description is None:
                    continue
                if description["error_code"] != 0:
                    error = _format_kafka_error(description["error_code"])
                    if kafka_errors.for_code(description["error_code"]).retriable:
                        retryable_errors.append(f"{name}: {error}")
                    else:
                        fatal_errors.append(f"{name}: {error}")
                    continue

                partitions = {partition["partition"]: partition for partition in description.get("partitions", [])}
                if 0 not in partitions:
                    missing_partitions.append(f"{name}[0]")
                    continue

                partition = partitions[0]
                if partition["error_code"] != 0:
                    error = _format_kafka_error(partition["error_code"])
                    if kafka_errors.for_code(partition["error_code"]).retriable:
                        retryable_errors.append(f"{name}[0]: {error}")
                    else:
                        fatal_errors.append(f"{name}[0]: {error}")
                    continue

                if partition.get("leader") in (-1, None):
                    leaderless_partitions.append(f"{name}[0]")

            if fatal_errors:
                raise AssertionError(f"Kafka topics {sorted(names)} reported non-retriable errors: {fatal_errors}")

            if not missing_topics and not missing_partitions and not leaderless_partitions and not retryable_errors:
                return

            last_error = ", ".join(
                part
                for part in (
                    f"missing topics={missing_topics}" if missing_topics else None,
                    f"missing partitions={missing_partitions}" if missing_partitions else None,
                    f"leaderless partitions={leaderless_partitions}" if leaderless_partitions else None,
                    f"retriable errors={retryable_errors}" if retryable_errors else None,
                )
                if part
            )

        if monotonic() >= deadline:
            _raise_kafka_timeout("topic readiness", names, last_error)
        sleep(KAFKA_POLL_INTERVAL_SECONDS)


def _wait_for_consumer_ready(consumer, names, monotonic=time.monotonic):
    deadline = monotonic() + KAFKA_READINESS_TIMEOUT_SECONDS
    expected_assignment = {TopicPartition(name, 0) for name in names}
    last_error = None
    original_request_timeout_ms = consumer.config.get("request_timeout_ms")
    consumer.config["request_timeout_ms"] = KAFKA_OPERATION_TIMEOUT_MS
    try:
        while True:
            consumer.poll(timeout_ms=KAFKA_READY_POLL_TIMEOUT_MS)
            assignment = consumer.assignment() or set()
            missing_assignment = sorted(
                (_format_topic_partition(topic_partition) for topic_partition in expected_assignment - assignment)
            )
            unexpected_assignment = sorted(
                (_format_topic_partition(topic_partition) for topic_partition in assignment - expected_assignment)
            )

            if not missing_assignment and not unexpected_assignment:
                try:
                    beginning_offsets = consumer.beginning_offsets(expected_assignment)
                    end_offsets = consumer.end_offsets(expected_assignment)
                except kafka_errors.KafkaError as exc:
                    last_error = repr(exc)
                    if not exc.retriable:
                        raise AssertionError(
                            f"Failed to resolve Kafka consumer offsets for {sorted(names)}: {last_error}"
                        ) from exc
                else:
                    missing_beginning_offsets = sorted(
                        _format_topic_partition(topic_partition)
                        for topic_partition in expected_assignment
                        if topic_partition not in beginning_offsets
                    )
                    missing_end_offsets = sorted(
                        _format_topic_partition(topic_partition)
                        for topic_partition in expected_assignment
                        if topic_partition not in end_offsets
                    )
                    if not missing_beginning_offsets and not missing_end_offsets:
                        return
                    last_error = ", ".join(
                        part
                        for part in (
                            (
                                f"missing beginning offsets={missing_beginning_offsets}"
                                if missing_beginning_offsets
                                else None
                            ),
                            f"missing end offsets={missing_end_offsets}" if missing_end_offsets else None,
                        )
                        if part
                    )
            else:
                last_error = ", ".join(
                    part
                    for part in (
                        f"missing assignment={missing_assignment}" if missing_assignment else None,
                        f"unexpected assignment={unexpected_assignment}" if unexpected_assignment else None,
                    )
                    if part
                )

            if monotonic() >= deadline:
                _raise_kafka_timeout("consumer readiness", names, last_error)
    finally:
        consumer.config["request_timeout_ms"] = original_request_timeout_ms


def _produce_records(producer, records, elasticapm_client=None, transaction_type=None):
    if (elasticapm_client is None) != (transaction_type is None):
        raise ValueError("elasticapm_client and transaction_type must be provided together")
    if elasticapm_client is not None and transaction_type is not None:
        elasticapm_client.begin_transaction(transaction_type)
    try:
        futures = [producer.send(topic, key=key, value=value) for topic, key, value in records]
        for future in futures:
            future.get(timeout=KAFKA_READINESS_TIMEOUT_SECONDS)
        producer.flush(timeout=KAFKA_READINESS_TIMEOUT_SECONDS)
    finally:
        if elasticapm_client is not None and transaction_type is not None:
            elasticapm_client.end_transaction(transaction_type)


def _consume_until_stop_iteration(consumer, on_message=None):
    messages = []
    iterator = iter(consumer)
    while True:
        try:
            message = next(iterator)
        except StopIteration:
            return messages
        messages.append(message)
        if on_message is not None:
            on_message(message)


def _capture_span(name):
    with elasticapm.capture_span(name):
        pass


@pytest.fixture(scope="function")
def topics():
    suffix = uuid.uuid4().hex
    topics = [f"test-{suffix}", f"foo-{suffix}", f"{suffix}-bar"]
    admin_client = KafkaAdminClient(
        bootstrap_servers=[KAFKA_BOOTSTRAP_SERVER],
        request_timeout_ms=KAFKA_OPERATION_TIMEOUT_MS,
        api_version_auto_timeout_ms=KAFKA_OPERATION_TIMEOUT_MS,
    )
    # Use unique topic names because Kafka topic deletion is asynchronous and fixed names can leak state between tests.
    try:
        _create_topics(admin_client, topics)
        _wait_for_topics_ready(admin_client, topics)
        yield topics
    finally:
        try:
            admin_client.delete_topics(topics, timeout_ms=KAFKA_OPERATION_TIMEOUT_MS)
        except kafka_errors.KafkaError as exc:
            warnings.warn(f"Failed to delete Kafka topics {sorted(topics)}: {exc!r}")
        finally:
            admin_client.close()


@pytest.fixture()
def producer(topics):
    producer = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVER)
    yield producer
    producer.close()


@pytest.fixture()
def consumer(topics):
    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVER,
        consumer_timeout_ms=KAFKA_CONSUME_TIMEOUT_MS,
        # Unique topics can be produced to before the consumer's initial offset is resolved.
        auto_offset_reset="earliest",
        request_timeout_ms=KAFKA_OPERATION_TIMEOUT_MS,
        api_version_auto_timeout_ms=KAFKA_OPERATION_TIMEOUT_MS,
    )
    try:
        consumer.subscribe(topics=topics)
        _wait_for_consumer_ready(consumer, topics)
        yield consumer
    finally:
        consumer.close()


def test_wait_for_topics_ready_rejects_missing_topics():
    class FakeAdminClient(object):
        def describe_topics(self, names):
            return []

    monotonic_values = iter((0, 8, 16))
    with pytest.raises(AssertionError, match="missing topics"):
        _wait_for_topics_ready(FakeAdminClient(), ["topic-a"], monotonic=lambda: next(monotonic_values), sleep=lambda _: None)


def test_wait_for_consumer_ready_rejects_partial_assignment():
    class FakeConsumer(object):
        config = {"request_timeout_ms": 1234}

        def poll(self, timeout_ms=0):
            return {}

        def assignment(self):
            return {TopicPartition("topic-a", 0)}

    monotonic_values = iter((0, 8, 16))
    with pytest.raises(AssertionError, match="missing assignment"):
        _wait_for_consumer_ready(
            FakeConsumer(),
            ["topic-a", "topic-b"],
            monotonic=lambda: next(monotonic_values),
        )


def test_kafka_produce(instrument, elasticapm_client, producer, topics):
    test_topic = topics[0]
    elasticapm_client.begin_transaction("test")
    producer.send(test_topic, key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.events[SPAN][0]
    assert span["name"] == f"Kafka SEND to {test_topic}"
    assert span["context"]["message"]["queue"]["name"] == test_topic
    assert span["context"]["destination"]["port"] == 9092
    assert span["context"]["destination"]["service"]["name"] == "kafka"
    assert span["context"]["destination"]["service"]["resource"] == f"kafka/{test_topic}"
    assert span["context"]["destination"]["service"]["type"] == "messaging"


def test_kafka_produce_ignore_topic(instrument, elasticapm_client, producer, topics):
    test_topic, foo_topic, bar_topic = topics
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")
    elasticapm_client.begin_transaction("test")
    producer.send(topic=foo_topic, key=b"foo", value=b"bar")
    producer.send(bar_topic, key=b"foo", value=b"bar")
    producer.send(test_topic, key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == f"Kafka SEND to {test_topic}"


def test_kafka_consume(instrument, elasticapm_client, producer, consumer, topics):
    test_topic = topics[0]
    _produce_records(
        producer,
        [(test_topic, b"foo", b"bar"), (test_topic, b"baz", b"bazzinga")],
        elasticapm_client=elasticapm_client,
        transaction_type="foo",
    )
    consumed_messages = _consume_until_stop_iteration(consumer, on_message=lambda _: _capture_span("foo"))
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    producer_transaction = next(transaction for transaction in transactions if transaction["type"] != "messaging")
    consumer_transactions = [transaction for transaction in transactions if transaction["type"] == "messaging"]
    consumer_spans = [span for span in spans if span["name"] == "foo"]
    assert len(consumed_messages) == 2
    # the consumer transactions should have the same trace id as the transaction that triggered the messages
    assert len(consumer_transactions) == 2
    assert len(consumer_spans) == 2
    assert (
        producer_transaction["trace_id"] == consumer_transactions[0]["trace_id"] == consumer_transactions[1]["trace_id"]
    )
    assert consumer_transactions[0]["name"] == f"Kafka RECEIVE from {test_topic}"
    assert consumer_transactions[0]["context"]["message"]["queue"]["name"] == test_topic

    assert consumer_spans[0]["transaction_id"] == consumer_transactions[0]["id"]
    assert consumer_spans[1]["transaction_id"] == consumer_transactions[1]["id"]


def test_kafka_consume_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    test_topic = topics[0]
    _produce_records(
        producer,
        [(test_topic, b"foo", b"bar"), (test_topic, b"baz", b"bazzinga")],
        elasticapm_client=elasticapm_client,
        transaction_type="foo",
    )
    elasticapm_client.begin_transaction("foo")
    consumed_messages = _consume_until_stop_iteration(consumer)
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    producer_transaction = next(
        transaction
        for transaction in transactions
        if any(span["name"] == f"Kafka SEND to {test_topic}" for span in elasticapm_client.spans_for_transaction(transaction))
    )
    external_transaction = next(
        transaction
        for transaction in transactions
        if any(
            span["name"] == f"Kafka RECEIVE from {test_topic}" for span in elasticapm_client.spans_for_transaction(transaction)
        )
    )
    producer_spans = elasticapm_client.spans_for_transaction(producer_transaction)
    receive_spans = elasticapm_client.spans_for_transaction(external_transaction)
    assert len(consumed_messages) == 2
    assert len(transactions) == 2
    assert len(producer_spans) == 2
    assert len(receive_spans) == 2
    assert {span["links"][0]["trace_id"] for span in receive_spans} == {producer_transaction["trace_id"]}
    assert {span["links"][0]["span_id"] for span in receive_spans} == {span["id"] for span in producer_spans}


def test_kafka_consumer_ignore_topic(instrument, elasticapm_client, producer, consumer, topics):
    test_topic, foo_topic, bar_topic = topics
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")
    _produce_records(
        producer,
        [(foo_topic, b"foo", b"bar"), (bar_topic, b"foo", b"bar"), (test_topic, b"foo", b"bar")],
    )
    consumed_messages = _consume_until_stop_iteration(consumer, on_message=lambda _: _capture_span("test"))
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(consumed_messages) == 3
    assert len(transactions) == 1
    assert transactions[0]["name"] == f"Kafka RECEIVE from {test_topic}"


def test_kafka_consumer_ignore_topic_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    test_topic, foo_topic, bar_topic = topics
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")
    _produce_records(
        producer,
        [(foo_topic, b"foo", b"bar"), (bar_topic, b"foo", b"bar"), (test_topic, b"foo", b"bar")],
    )
    elasticapm_client.begin_transaction("foo")
    consumed_messages = _consume_until_stop_iteration(consumer)
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert len(consumed_messages) == 3
    assert len(spans) == 1
    assert spans[0]["name"] == f"Kafka RECEIVE from {test_topic}"


def test_kafka_poll_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    test_topic = topics[0]
    _produce_records(producer, [(test_topic, b"foo", b"bar"), (test_topic, b"baz", b"bazzinga")])
    elasticapm_client.begin_transaction("foo")
    results = consumer.poll(timeout_ms=1000)
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    assert sum(len(records) for records in results.values()) == 2
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka POLL from " + ", ".join(sorted(topics))


def test_kafka_no_client(instrument, producer, consumer, topics):
    test_topic = topics[0]
    assert elasticapm.get_client() is None
    # the following code shouldn't trigger any errors
    producer.send(test_topic, key=b"foo", value=b"bar")
    for item in consumer:
        pass


def test_kafka_send_unsampled_transaction(instrument, elasticapm_client, producer, topics):
    test_topic = topics[0]
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    producer.send(test_topic, key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


def test_kafka_poll_unsampled_transaction(instrument, elasticapm_client, consumer, topics):
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    consumer.poll(timeout_ms=50)
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 0


def test_kafka_consumer_unsampled_transaction_handles_stop_iteration(
    instrument, elasticapm_client, producer, consumer, topics
):
    test_topic = topics[0]
    _produce_records(producer, [(test_topic, b"foo", b"bar")])
    transaction = elasticapm_client.begin_transaction("foo")
    transaction.is_sampled = False
    consumed_messages = _consume_until_stop_iteration(consumer)
    elasticapm_client.end_transaction("foo")
    spans = elasticapm_client.events[SPAN]
    assert len(consumed_messages) == 1
    assert len(spans) == 0
