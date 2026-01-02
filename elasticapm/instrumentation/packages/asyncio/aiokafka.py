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

import time
from collections.abc import Awaitable, Callable, Container, Iterable, MutableSequence
from enum import IntEnum
from typing import TYPE_CHECKING, Dict, List, Optional, TypeVar, cast

from elasticapm import Client, get_client
from elasticapm.conf.constants import OUTCOME, TRACEPARENT_BINARY_HEADER_NAME
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, Span, Transaction, capture_span, execution_context
from elasticapm.utils.disttracing import TraceParent

if TYPE_CHECKING:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRecord, TopicPartition  # pragma: no cover


class _KafkaTimestampType(IntEnum):
    NO_TIMESTAMP_TYPE = -1
    CREATE_TIME = 0
    LOG_APPEND_TIME = 1


class AIOKafkaInstrumentation(AsyncAbstractInstrumentedModule):
    """Instrument the aiokafka's consumer and producer

    Features:
    - Like KafkaInstrumentation, if no transaction is active, it begins a new
      transaction on asynchronous iteration over the consumer.
    - Unlike KafkaInstrumentation, when an active transaction exists, it even
      records StopAsyncIteration on asynchronous iteration over the consumer as
      a span.
    - It does not support automatic trace context propagation for messages
      being sent via send_batch().
    """

    instrument_list = [
        ("aiokafka", "AIOKafkaConsumer.getone"),
        ("aiokafka", "AIOKafkaConsumer.getmany"),
        ("aiokafka", "AIOKafkaProducer.send"),
        ("aiokafka", "AIOKafkaProducer.send_batch"),
        ("aiokafka", "AIOKafkaConsumer.__anext__"),
    ]
    name = "aiokafka"
    creates_transactions = True

    SPAN_TYPE = SERVICE_TYPE = TRANSACTION_TYPE = "messaging"
    SPAN_SUBTYPE = SERVICE_NAME = "kafka"

    T_Result = TypeVar("T_Result")

    async def call(
        self,
        module: str,
        method: str,
        wrapped: Callable[..., Awaitable[T_Result]],
        instance: Optional[object],
        args: tuple,
        kwargs: dict,
    ) -> T_Result:

        client = get_client()
        if not client:
            return await wrapped(*args, **kwargs)

        transaction = execution_context.get_transaction()

        if method == "AIOKafkaConsumer.__anext__":
            # If no transaction exists, we create and start new ones implicitly
            # like we do in KafkaInstrumentation.

            if transaction and transaction.transaction_type != self.TRANSACTION_TYPE:
                # Somebody started a transaction outside of the consumer,
                # so we will only capture subsequent getone() as a span.
                return await wrapped(*args, **kwargs)

            # No transaction running, or this is a transaction started by us,
            # so let's end it and start the next,
            # unless a StopAsyncIteration is raised, at which point we do nothing.
            if transaction:
                client.end_transaction(result=OUTCOME.SUCCESS)

            # May raise StopAsyncIteration
            result = await wrapped(*args, **kwargs)
            message = cast("ConsumerRecord", result)

            if client.should_ignore_topic(message.topic):
                return result

            trace_parent = _extract_trace_parent_from_message_headers(message.headers)
            transaction = client.begin_transaction(self.TRANSACTION_TYPE, trace_parent=trace_parent)

            if not transaction:
                return result

            transaction.name = f"Kafka RECEIVE from {message.topic}"
            self._enrich_transaction_context(
                transaction, message.topic, timestamp_type=message.timestamp_type, timestamp=message.timestamp
            )

            return result

        elif not transaction:
            return await wrapped(*args, **kwargs)

        elif method.startswith("AIOKafkaConsumer.get"):
            return await self._trace_get(
                wrapped,
                cast(Optional["AIOKafkaConsumer"], instance),
                args,
                kwargs,
                client=client,
            )

        else:
            return await self._trace_send(
                wrapped,
                cast(Optional["AIOKafkaProducer"], instance),
                args,
                kwargs,
                client=client,
                trace_parent=transaction.trace_parent,
            )

    @classmethod
    async def _trace_get(
        cls,
        wrapped: Callable[..., Awaitable[T_Result]],
        instance: Optional["AIOKafkaConsumer"],
        args: tuple,
        kwargs: dict,
        *,
        client: Client,
    ) -> T_Result:
        """Trace the consumer's get() and getmany() by capturing a span"""

        with capture_span(
            name="Kafka RECEIVE",
            leaf=True,
            span_type=cls.SPAN_TYPE,
            span_subtype=cls.SPAN_SUBTYPE,
            span_action="receive",
        ) as span:

            result = await wrapped(*args, **kwargs)

            if not span or isinstance(span, DroppedSpan):
                return result

            trace_topics = [
                topic for topic in _extract_topics_from_get_result(result) if not client.should_ignore_topic(topic)
            ]

            if not trace_topics:
                span.cancel()
                return result

            span.name += f" from {', '.join(trace_topics)}"
            cls._enrich_span_context(span, *trace_topics, consumer=instance)

            for message in _extract_messages_from_get_result(result, include_topics=trace_topics):
                trace_parent = _extract_trace_parent_from_message_headers(message.headers)
                if trace_parent:
                    span.add_link(trace_parent)

            return result

    @classmethod
    async def _trace_send(
        cls,
        wrapped: Callable[..., Awaitable[T_Result]],
        instance: Optional["AIOKafkaProducer"],
        args: tuple,
        kwargs: dict,
        *,
        client: Client,
        trace_parent: TraceParent,
    ) -> T_Result:
        """Trace the producer's send() and send_batch() by capturing a span"""

        topic = _extract_topic_from_send_arguments(args, kwargs)
        if client.should_ignore_topic(topic):
            return await wrapped(*args, **kwargs)

        with capture_span(
            name=f"Kafka SEND to {topic}",
            leaf=True,
            span_type=cls.SPAN_TYPE,
            span_subtype=cls.SPAN_SUBTYPE,
            span_action="send",
        ) as span:

            if span and not isinstance(span, DroppedSpan):
                trace_parent = trace_parent.copy_from(span_id=span.id)

            mutable_args = list(args)
            _inject_trace_parent_into_send_arguments(mutable_args, kwargs, trace_parent)

            result = await wrapped(*mutable_args, **kwargs)

            if span and not isinstance(span, DroppedSpan):
                cls._enrich_span_context(span, topic, producer=instance)

            return result

    @classmethod
    def _enrich_span_context(
        cls,
        span: Span,
        topic: str,
        *topics: str,
        producer: Optional["AIOKafkaProducer"] = None,
        consumer: Optional["AIOKafkaConsumer"] = None,
    ):

        destination_service = {"type": cls.SERVICE_TYPE, "name": cls.SERVICE_NAME}
        service_framework = {"name": "Kafka"}

        span.context.setdefault("destination", {}).setdefault("service", {}).update(destination_service)
        span.context.setdefault("service", {}).setdefault("framework", {}).update(service_framework)

        if not topics:
            span.context["destination"]["service"]["resource"] = f"{cls.SERVICE_NAME}/{topic}"
            span.context.setdefault("message", {}).setdefault("queue", {}).update({"name": topic})

        if producer and producer.client.cluster.controller:
            span.context["destination"]["address"] = producer.client.cluster.controller.host
            span.context["destination"]["port"] = producer.client.cluster.controller.port

    @classmethod
    def _enrich_transaction_context(
        cls,
        transaction: Transaction,
        topic: str,
        *,
        timestamp_type: int,
        timestamp: int,
    ):

        destination_service = {
            "type": cls.SERVICE_TYPE,
            "name": cls.SERVICE_NAME,
            "resource": f"{cls.SERVICE_NAME}/{topic}",
        }
        message_queue = {"name": topic}
        service_framework = {"name": "Kafka"}

        transaction.context.setdefault("destination", {}).setdefault("service", {}).update(destination_service)
        transaction.context.setdefault("message", {}).setdefault("queue", {}).update(message_queue)
        transaction.context.setdefault("service", {}).setdefault("framework", {}).update(service_framework)

        if timestamp_type == _KafkaTimestampType.CREATE_TIME:
            current_time_millis = int(round(time.time() * 1000))
            age = current_time_millis - timestamp
            transaction.context["message"].setdefault("age", {}).update({"ms": age})


def _extract_trace_parent_from_message_headers(headers: Optional[Iterable]) -> Optional[TraceParent]:

    for key, value in headers or []:
        if key == TRACEPARENT_BINARY_HEADER_NAME:
            return TraceParent.from_binary(value)

    return None


def _extract_topics_from_get_result(result) -> Iterable[str]:

    if hasattr(result, "topic"):
        message = cast("ConsumerRecord", result)  # from getone()
        yield message.topic

    else:
        messages = cast(Dict["TopicPartition", List["ConsumerRecord"]], result)  # from getmany()
        for topic_partition in messages:
            yield topic_partition.topic


def _extract_messages_from_get_result(result, *, include_topics: Container[str] = ()) -> Iterable["ConsumerRecord"]:

    if hasattr(result, "topic"):
        message = cast("ConsumerRecord", result)  # from getone()
        if message.topic in include_topics:
            yield message

    else:
        messages = cast(Dict["TopicPartition", List["ConsumerRecord"]], result)  # from getmany()
        for topic_partition in messages:
            if topic_partition.topic not in include_topics:
                continue
            yield from messages[topic_partition]


def _has_append_method(obj: object) -> bool:

    return hasattr(obj, "append") and callable(getattr(obj, "append"))


def _extract_topic_from_send_arguments(args: tuple, kwargs: dict) -> str:

    if "topic" in kwargs:
        return kwargs["topic"]

    elif _has_append_method(args[0]):
        # The first argument of the producer's send_batch() may be 'BatchBuilder'
        # which has 'append' method. If that's the case, the second one is 'topic'.
        return args[1]

    return args[0]


def _inject_trace_parent_into_send_arguments(args: list, kwargs: dict, trace_parent: TraceParent):

    if "batch" in kwargs or args and _has_append_method(args[0]):
        return  # Injection is not practical as messages are already encoded in the batch

    if "headers" in kwargs:
        headers = kwargs["headers"]
        if headers is None:
            headers = kwargs["headers"] = []

    else:
        # headers is the 6th parameter in send()
        headers_position_in_args = 5  # 6th parameter, 0-indexed
        for preceding_parameter in ["topic", "value", "key", "partition", "timestamp_ms"]:
            if preceding_parameter in kwargs:
                headers_position_in_args -= 1

        try:
            headers = args[headers_position_in_args]
        except IndexError:
            headers = kwargs["headers"] = []
        else:
            if headers is None:
                headers = args[headers_position_in_args] = []

    if not isinstance(headers, MutableSequence):
        # headers may also be a tuple, for example
        raise TypeError(f"'headers' is not a MutableSequence, got {type(headers).__name__}")

    # Injecting trace parent after removing any existing one; Here, we retain
    # even a header with zero elements as we are not in a position to remove it.
    headers[:] = [header for header in headers if not header or header[0] != TRACEPARENT_BINARY_HEADER_NAME]
    headers.append((TRACEPARENT_BINARY_HEADER_NAME, trace_parent.to_binary()))
