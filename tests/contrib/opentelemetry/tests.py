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

pytest.importorskip("opentelemetry.sdk")  # isort:skip

from opentelemetry.trace import Link, SpanContext, SpanKind, TraceFlags
from opentelemetry.trace.propagation import _SPAN_KEY

import elasticapm.contrib.opentelemetry.context as context
import elasticapm.contrib.opentelemetry.trace as trace
from elasticapm.conf import constants
from elasticapm.contrib.opentelemetry.trace import Tracer

pytestmark = pytest.mark.opentelemetry


@pytest.fixture
def tracer(elasticapm_client) -> Tracer:
    yield Tracer("test", elasticapm_client=elasticapm_client)


def test_root_transaction(tracer: Tracer):
    with tracer.start_as_current_span("test"):
        pass

    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    assert transaction["type"] == "unknown"
    assert transaction["name"] == "test"
    assert transaction["result"] == "OK"


def test_ot_span(tracer: Tracer):
    with tracer.start_as_current_span("test"):
        with tracer.start_as_current_span("testspan", kind=SpanKind.CONSUMER):
            with tracer.start_as_current_span("testspan2"):
                pass
    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    span1 = client.events[constants.SPAN][1]
    span2 = client.events[constants.SPAN][0]
    assert span1["transaction_id"] == span1["parent_id"] == transaction["id"]
    assert span1["name"] == "testspan"

    assert span2["transaction_id"] == transaction["id"]
    assert span2["parent_id"] == span1["id"]
    assert span2["name"] == "testspan2"


def test_ot_span_without_auto_attach(tracer: Tracer):
    with tracer.start_as_current_span("test"):
        span = tracer.start_span("testspan", kind=SpanKind.CONSUMER)
        with tracer.start_as_current_span("testspan2"):
            pass
        with trace.use_span(span, end_on_exit=True):
            with tracer.start_as_current_span("testspan3"):
                pass
    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    # The spans come in out of the normal/intuitive order, since "testspan2" ends first.
    span1 = client.events[constants.SPAN][2]
    span2 = client.events[constants.SPAN][0]
    span3 = client.events[constants.SPAN][1]
    assert span1["transaction_id"] == span1["parent_id"] == transaction["id"]
    assert span1["name"] == "testspan"

    assert span2["transaction_id"] == span2["parent_id"] == transaction["id"]
    assert span2["name"] == "testspan2"

    assert span3["transaction_id"] == transaction["id"]
    assert span3["parent_id"] == span1["id"]
    assert span3["name"] == "testspan3"


def test_ot_transaction_types(tracer: Tracer):
    with tracer.start_as_current_span(
        "test_request", attributes={"http.url": "http://localhost"}, kind=SpanKind.SERVER
    ):
        pass
    with tracer.start_as_current_span(
        "test_messaging", attributes={"messaging.system": "kafka"}, kind=SpanKind.CONSUMER
    ):
        pass
    client = tracer.client
    transaction1 = client.events[constants.TRANSACTION][0]
    transaction2 = client.events[constants.TRANSACTION][1]
    assert transaction1["type"] == "request"
    assert transaction2["type"] == "messaging"

    assert transaction1["otel"]["span_kind"] == "SERVER"
    assert transaction1["otel"]["attributes"]["http.url"] == "http://localhost"


def test_ot_exception(tracer: Tracer):
    with pytest.raises(Exception):
        with tracer.start_as_current_span("test"):
            raise Exception()

    client = tracer.client
    error = client.events[constants.ERROR][0]
    assert error["context"]["otel_spankind"] == "INTERNAL"


def test_ot_spancontext(tracer: Tracer):
    with tracer.start_as_current_span("test") as ot_span:
        span_context = ot_span.get_span_context()
    assert isinstance(span_context, SpanContext)
    assert span_context.trace_id
    assert span_context.trace_flags.sampled == TraceFlags.SAMPLED


def test_span_links(tracer: Tracer):
    span_context = SpanContext(
        trace_id=int("aabbccddeeff00112233445566778899", 16), span_id=int("0011223344556677", 16), is_remote=False
    )
    link = Link(span_context)
    with tracer.start_as_current_span("testtransaction", links=[link]):
        with tracer.start_as_current_span("testspan", links=[link]):
            pass
    client = tracer.client
    transaction = client.events[constants.TRANSACTION][0]
    span = client.events[constants.SPAN][0]
    assert transaction["links"][0]["trace_id"] == "aabbccddeeff00112233445566778899"
    assert transaction["links"][0]["span_id"] == "0011223344556677"
    assert span["links"][0]["trace_id"] == "aabbccddeeff00112233445566778899"
    assert span["links"][0]["span_id"] == "0011223344556677"


# TODO Add some span subtype testing?
