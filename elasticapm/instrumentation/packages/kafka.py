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
from typing import Optional

import elasticapm
from elasticapm import get_client
from elasticapm.conf import constants
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import DroppedSpan, capture_span, execution_context
from elasticapm.utils.disttracing import TraceParent, TracingOptions


class KafkaInstrumentation(AbstractInstrumentedModule):

    instrument_list = [
        ("kafka", "KafkaProducer.send"),
        ("kafka", "KafkaConsumer.poll"),
        ("kafka", "KafkaConsumer.__next__"),
    ]
    provider_name = "kafka"
    name = "kafka"
    creates_transactions = True

    def _trace_send(self, instance, wrapped, *args, destination_info=None, **kwargs):
        topic = args[0] if args else kwargs["topic"]
        headers = args[4] if len(args) > 4 else kwargs.get("headers", None)

        span_name = f"Kafka SEND to {topic}"
        destination_info["service"]["resource"] += topic
        with capture_span(
            name=span_name,
            span_type="messaging",
            span_subtype=self.provider_name,
            span_action="send",
            leaf=True,
            extra={
                "message": {"queue": {"name": topic}},
                "destination": destination_info,
            },
        ) as span:
            transaction = execution_context.get_transaction()
            if transaction:
                tp = transaction.trace_parent.copy_from(
                    span_id=span.id if span else transaction.id,
                    trace_options=None if span else TracingOptions(recorded=False),
                )
            if headers:
                headers.append((constants.TRACEPARENT_BINARY_HEADER_NAME, tp.to_binary()))
            else:
                headers = [(constants.TRACEPARENT_BINARY_HEADER_NAME, tp.to_binary())]
                if len(args) > 4:
                    args = list(args)
                    args[4] = headers
                else:
                    kwargs["headers"] = headers
            result = wrapped(*args, **kwargs)
            if span and instance and instance._metadata.controller and not isinstance(span, DroppedSpan):
                address = instance._metadata.controller[1]
                port = instance._metadata.controller[2]
                span.context["destination"]["address"] = address
                span.context["destination"]["port"] = port
            return result

    def call(self, module, method, wrapped, instance, args, kwargs):
        client = get_client()
        if client is None:
            return wrapped(*args, **kwargs)
        destination_info = {
            "service": {"name": "kafka", "resource": "kafka/", "type": "messaging"},
        }

        if method == "KafkaProducer.send":
            topic = args[0] if args else kwargs["topic"]
            if client.should_ignore_topic(topic) or not execution_context.get_transaction():
                return wrapped(*args, **kwargs)
            return self._trace_send(instance, wrapped, destination_info=destination_info, *args, **kwargs)

        elif method == "KafkaConsumer.poll":
            transaction = execution_context.get_transaction()
            if transaction:
                with capture_span(
                    name="Kafka POLL",
                    span_type="messaging",
                    span_subtype=self.provider_name,
                    span_action="poll",
                    leaf=True,
                    extra={
                        "destination": destination_info,
                    },
                ) as span:
                    if span and not isinstance(span, DroppedSpan) and instance._subscription.subscription:
                        span.name += " from " + ", ".join(sorted(instance._subscription.subscription))
                    results = wrapped(*args, **kwargs)
                    return results
            else:
                return wrapped(*args, **kwargs)

        elif method == "KafkaConsumer.__next__":
            transaction = execution_context.get_transaction()
            if transaction and transaction.transaction_type != "messaging":
                # somebody started a transaction outside of the consumer,
                # so we capture it as a span, and record the causal trace as a link
                with capture_span(
                    name="consumer",
                    span_type="messaging",
                    span_subtype=self.provider_name,
                    span_action="receive",
                    leaf=True,
                    extra={
                        "message": {"queue": {"name": ""}},
                        "destination": destination_info,
                    },
                ) as span:
                    try:
                        result = wrapped(*args, **kwargs)
                    except StopIteration:
                        span.cancel()
                        raise
                    if span and not isinstance(span, DroppedSpan):
                        topic = result[0]
                        if client.should_ignore_topic(topic):
                            span.cancel()
                            return result
                        trace_parent = self.get_traceparent_from_result(result)
                        if trace_parent:
                            span.add_link(trace_parent)
                        destination_info["service"]["resource"] += topic
                        span.context["message"]["queue"]["name"] = topic
                        span.name = "Kafka RECEIVE from " + topic
                    return result
            else:
                # No transaction running, or this is a transaction started by us,
                # so let's end it and start the next,
                # unless a StopIteration is raised, at which point we do nothing.
                if transaction:
                    client.end_transaction()
                result = wrapped(*args, **kwargs)
                topic = result[0]
                if client.should_ignore_topic(topic):
                    return result
                trace_parent = self.get_traceparent_from_result(result)
                transaction = client.begin_transaction("messaging", trace_parent=trace_parent)
                if result.timestamp_type == 0:
                    current_time_millis = int(round(time.time() * 1000))
                    age = current_time_millis - result.timestamp
                    transaction.context = {
                        "message": {"age": {"ms": age}, "queue": {"name": topic}},
                        "service": {"framework": {"name": "Kafka"}},
                    }
                transaction_name = "Kafka RECEIVE from " + topic
                elasticapm.set_transaction_name(transaction_name, override=True)
                res = constants.OUTCOME.SUCCESS
                elasticapm.set_transaction_result(res, override=False)
                return result

    def get_traceparent_from_result(self, result) -> Optional[TraceParent]:
        for k, v in result.headers:
            if k == constants.TRACEPARENT_BINARY_HEADER_NAME:
                return TraceParent.from_binary(v)
