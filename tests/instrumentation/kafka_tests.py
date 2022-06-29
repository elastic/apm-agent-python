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

import datetime
import os
import threading
import time

import pytest

import elasticapm
from elasticapm.conf.constants import SPAN, TRANSACTION

kafka = pytest.importorskip("kafka")

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

pytestmark = [pytest.mark.kafka]

if "KAFKA_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping kafka tests, no KAFKA_HOST environment variable set"))

KAFKA_HOST = os.environ["KAFKA_HOST"]


@pytest.fixture(scope="function")
def topics():
    topics = ["test", "foo", "bar"]
    admin_client = KafkaAdminClient(bootstrap_servers=[f"{KAFKA_HOST}:9092"])
    admin_client.create_topics([NewTopic(name, num_partitions=1, replication_factor=1) for name in topics])
    yield topics
    admin_client.delete_topics(topics)


@pytest.fixture()
def producer():
    producer = KafkaProducer(bootstrap_servers=f"{KAFKA_HOST}:9092")
    yield producer


@pytest.fixture()
def consumer():
    consumer = KafkaConsumer(bootstrap_servers=f"{KAFKA_HOST}:9092", consumer_timeout_ms=500)
    consumer.subscribe(topics=["foo", "bar", "test"])
    yield consumer


def test_kafka_produce(instrument, elasticapm_client, producer, topics):
    elasticapm_client.begin_transaction("test")
    producer.send("test", key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.events[SPAN][0]
    assert span["name"] == "Kafka SEND to test"
    assert span["context"]["message"]["queue"]["name"] == "test"
    assert span["context"]["destination"]["port"] == 9092
    assert span["context"]["destination"]["service"]["name"] == "kafka"
    assert span["context"]["destination"]["service"]["resource"] == "kafka/test"
    assert span["context"]["destination"]["service"]["type"] == "messaging"


def test_kafka_produce_ignore_topic(instrument, elasticapm_client, producer, topics):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")
    elasticapm_client.begin_transaction("test")
    producer.send(topic="foo", key=b"foo", value=b"bar")
    producer.send("bar", key=b"foo", value=b"bar")
    producer.send("test", key=b"foo", value=b"bar")
    elasticapm_client.end_transaction("test", "success")
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka SEND to test"


def test_kafka_consume(instrument, elasticapm_client, producer, consumer, topics):
    def delayed_send():
        time.sleep(0.2)
        elasticapm_client.begin_transaction("foo")
        producer.send("test", key=b"foo", value=b"bar")
        producer.send("test", key=b"baz", value=b"bazzinga")
        elasticapm_client.end_transaction("foo")

    thread = threading.Thread(target=delayed_send)
    thread.start()
    for item in consumer:
        with elasticapm.capture_span("foo"):
            pass
    thread.join()
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    # the consumer transactions should have the same trace id as the transaction that triggered the messages
    assert transactions[0]["trace_id"] == transactions[1]["trace_id"] == transactions[2]["trace_id"]
    assert transactions[1]["name"] == "Kafka RECEIVE from test"
    assert transactions[1]["type"] == "messaging"
    assert transactions[1]["context"]["message"]["queue"]["name"] == "test"

    assert spans[2]["transaction_id"] == transactions[1]["id"]
    assert spans[3]["transaction_id"] == transactions[2]["id"]


def test_kafka_consume_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    def delayed_send():
        time.sleep(0.2)
        elasticapm_client.begin_transaction("foo")
        producer.send("test", key=b"foo", value=b"bar")
        producer.send("test", key=b"baz", value=b"bazzinga")
        elasticapm_client.end_transaction("foo")

    thread = threading.Thread(target=delayed_send)
    thread.start()
    transaction = elasticapm_client.begin_transaction("foo")
    for item in consumer:
        pass
    thread.join()
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 2
    external_spans = elasticapm_client.spans_for_transaction(transactions[0])
    spans = elasticapm_client.spans_for_transaction(transactions[1])
    assert len(external_spans) == 2
    assert len(spans) == 2
    assert spans[0]["links"][0]["trace_id"] == external_spans[0]["trace_id"]
    assert spans[1]["links"][0]["trace_id"] == external_spans[1]["trace_id"]


def test_kafka_consumer_ignore_topic(instrument, elasticapm_client, producer, consumer, topics):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")

    def delayed_send():
        time.sleep(0.2)
        producer.send(topic="foo", key=b"foo", value=b"bar")
        producer.send("bar", key=b"foo", value=b"bar")
        producer.send("test", key=b"foo", value=b"bar")

    thread = threading.Thread(target=delayed_send)
    thread.start()
    for item in consumer:
        with elasticapm.capture_span("test"):
            assert item
    thread.join()
    transactions = elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 1
    assert transactions[0]["name"] == "Kafka RECEIVE from test"


def test_kafka_consumer_ignore_topic_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    elasticapm_client.config.update("1", ignore_message_queues="foo*,*bar")

    def delayed_send():
        time.sleep(0.2)
        producer.send(topic="foo", key=b"foo", value=b"bar")
        producer.send("bar", key=b"foo", value=b"bar")
        producer.send("test", key=b"foo", value=b"bar")

    thread = threading.Thread(target=delayed_send)
    thread.start()
    transaction = elasticapm_client.begin_transaction("foo")
    for item in consumer:
        pass
    thread.join()
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka RECEIVE from test"


def test_kafka_poll_ongoing_transaction(instrument, elasticapm_client, producer, consumer, topics):
    def delayed_send():
        time.sleep(0.2)
        producer.send("test", key=b"foo", value=b"bar")
        producer.send("test", key=b"baz", value=b"bazzinga")

    thread = threading.Thread(target=delayed_send)
    thread.start()
    transaction = elasticapm_client.begin_transaction("foo")
    results = consumer.poll(timeout_ms=1000)
    elasticapm_client.end_transaction("foo")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.events[SPAN]
    assert len(spans) == 1
    assert spans[0]["name"] == "Kafka POLL from bar, foo, test"


def test_kafka_no_client(instrument, producer, consumer, topics):
    assert elasticapm.get_client() is None
    # the following code shouldn't trigger any errors
    producer.send("test", key=b"foo", value=b"bar")
    for item in consumer:
        pass


def test_kafka_send_unsampled_transaction(instrument, elasticapm_client, producer, topics):
    transaction_object = elasticapm_client.begin_transaction("transaction")
    transaction_object.is_sampled = False
    producer.send("test", key=b"foo", value=b"bar")
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
