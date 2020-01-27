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

opentracing = pytest.importorskip("opentracing")  # isort:skip

import sys

import mock
from opentracing import Format

from elasticapm.conf import constants
from elasticapm.contrib.opentracing import Tracer
from elasticapm.contrib.opentracing.span import OTSpanContext
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.opentracing


try:
    from opentracing import logs as ot_logs
    from opentracing import tags
except ImportError:
    ot_logs = None


@pytest.fixture()
def tracer(elasticapm_client):
    yield Tracer(client_instance=elasticapm_client)


def test_tracer_with_instantiated_client(elasticapm_client):
    tracer = Tracer(client_instance=elasticapm_client)
    assert tracer._agent is elasticapm_client


def test_tracer_with_config():
    config = {"METRICS_INTERVAL": "0s", "SERVER_URL": "https://example.com/test"}
    tracer = Tracer(config=config)
    try:
        assert tracer._agent.config.metrics_interval == 0
        assert tracer._agent.config.server_url == "https://example.com/test"
    finally:
        tracer._agent.close()


def test_tracer_instrument(elasticapm_client):
    with mock.patch("elasticapm.contrib.opentracing.tracer.instrument") as mock_instrument:
        elasticapm_client.config.instrument = False
        Tracer(client_instance=elasticapm_client)
        assert mock_instrument.call_count == 0

        elasticapm_client.config.instrument = True
        Tracer(client_instance=elasticapm_client)
        assert mock_instrument.call_count == 1


def test_ot_transaction_started(tracer):
    with tracer.start_active_span("test") as ot_scope:
        ot_scope.span.set_tag("result", "OK")
    client = tracer._agent
    transaction = client.events[constants.TRANSACTION][0]
    assert transaction["type"] == "custom"
    assert transaction["name"] == "test"
    assert transaction["result"] == "OK"


def test_ot_span(tracer):
    with tracer.start_active_span("test") as ot_scope_transaction:
        with tracer.start_active_span("testspan") as ot_scope_span:
            ot_scope_span.span.set_tag("span.kind", "custom")
            with tracer.start_active_span("testspan2") as ot_scope_span2:
                with tracer.start_active_span("testspan3", child_of=ot_scope_span.span) as ot_scope_span3:
                    pass
    client = tracer._agent
    transaction = client.events[constants.TRANSACTION][0]
    span1 = client.events[constants.SPAN][2]
    span2 = client.events[constants.SPAN][1]
    span3 = client.events[constants.SPAN][0]
    assert span1["transaction_id"] == span1["parent_id"] == transaction["id"]
    assert span1["name"] == "testspan"

    assert span2["transaction_id"] == transaction["id"]
    assert span2["parent_id"] == span1["id"]
    assert span2["name"] == "testspan2"

    # check that span3 has span1 as parent
    assert span3["transaction_id"] == transaction["id"]
    assert span3["parent_id"] == span1["id"]
    assert span3["name"] == "testspan3"


def test_transaction_tags(tracer):
    with tracer.start_active_span("test") as ot_scope:
        ot_scope.span.set_tag("type", "foo")
        ot_scope.span.set_tag("http.status_code", 200)
        ot_scope.span.set_tag("http.url", "http://example.com/foo")
        ot_scope.span.set_tag("http.method", "GET")
        ot_scope.span.set_tag("user.id", 1)
        ot_scope.span.set_tag("user.email", "foo@example.com")
        ot_scope.span.set_tag("user.username", "foo")
        ot_scope.span.set_tag("component", "Django")
        ot_scope.span.set_tag("something.else", "foo")
    client = tracer._agent
    transaction = client.events[constants.TRANSACTION][0]

    assert transaction["type"] == "foo"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["context"]["response"]["status_code"] == 200
    assert transaction["context"]["request"]["url"]["full"] == "http://example.com/foo"
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["user"] == {"id": 1, "email": "foo@example.com", "username": "foo"}
    assert transaction["context"]["service"]["framework"]["name"] == "Django"
    assert transaction["context"]["tags"] == {"something_else": "foo"}


def test_span_tags(tracer):
    with tracer.start_active_span("transaction") as ot_scope_t:
        with tracer.start_active_span("span") as ot_scope_s:
            s = ot_scope_s.span
            s.set_tag("db.type", "sql")
            s.set_tag("db.statement", "SELECT * FROM foo")
            s.set_tag("db.user", "bar")
            s.set_tag("db.instance", "baz")
        with tracer.start_active_span("span") as ot_scope_s:
            s = ot_scope_s.span
            s.set_tag("span.kind", "foo")
            s.set_tag("something.else", "bar")
    client = tracer._agent
    span1 = client.events[constants.SPAN][0]
    span2 = client.events[constants.SPAN][1]

    assert span1["context"]["db"] == {"type": "sql", "user": "bar", "statement": "SELECT * FROM foo"}
    assert span1["type"] == "db.sql"
    assert span1["context"]["tags"] == {"db_instance": "baz"}

    assert span2["type"] == "foo"
    assert span2["context"]["tags"] == {"something_else": "bar"}


@pytest.mark.parametrize("elasticapm_client", [{"transaction_max_spans": 1}], indirect=True)
def test_dropped_spans(tracer):
    assert tracer._agent.config.transaction_max_spans == 1
    with tracer.start_active_span("transaction") as ot_scope_t:
        with tracer.start_active_span("span") as ot_scope_s:
            s = ot_scope_s.span
            s.set_tag("db.type", "sql")
        with tracer.start_active_span("span") as ot_scope_s:
            s = ot_scope_s.span
            s.set_tag("db.type", "sql")
    client = tracer._agent
    spans = client.events[constants.SPAN]
    assert len(spans) == 1


def test_error_log(tracer):
    with tracer.start_active_span("transaction") as tx_scope:
        try:
            raise ValueError("oops")
        except ValueError:
            exc_type, exc_val, exc_tb = sys.exc_info()[:3]
            tx_scope.span.log_kv(
                {"python.exception.type": exc_type, "python.exception.val": exc_val, "python.exception.tb": exc_tb}
            )
    client = tracer._agent
    error = client.events[constants.ERROR][0]

    assert error["exception"]["message"] == "ValueError: oops"


@pytest.mark.skipif(ot_logs is None, reason="New key names in opentracing-python 2.1")
def test_error_log_ot_21(tracer):
    with tracer.start_active_span("transaction") as tx_scope:
        try:
            raise ValueError("oops")
        except ValueError:
            exc_type, exc_val, exc_tb = sys.exc_info()[:3]
            tx_scope.span.log_kv(
                {
                    ot_logs.EVENT: tags.ERROR,
                    ot_logs.ERROR_KIND: exc_type,
                    ot_logs.ERROR_OBJECT: exc_val,
                    ot_logs.STACK: exc_tb,
                }
            )
    client = tracer._agent
    error = client.events[constants.ERROR][0]

    assert error["exception"]["message"] == "ValueError: oops"


def test_error_log_automatic_in_span_context_manager(tracer):
    scope = tracer.start_active_span("transaction")
    with pytest.raises(ValueError):
        with scope.span:
            raise ValueError("oops")

    client = tracer._agent
    error = client.events[constants.ERROR][0]

    assert error["exception"]["message"] == "ValueError: oops"


def test_span_set_bagge_item_noop(tracer):
    scope = tracer.start_active_span("transaction")
    assert scope.span.set_baggage_item("key", "val") == scope.span


def test_tracer_extract_http(tracer):
    span_context = tracer.extract(
        Format.HTTP_HEADERS, {"elastic-apm-traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    )

    assert span_context.trace_parent.version == 0
    assert span_context.trace_parent.trace_id == "0af7651916cd43dd8448eb211c80319c"
    assert span_context.trace_parent.span_id == "b7ad6b7169203331"


def test_tracer_extract_map(tracer):
    span_context = tracer.extract(
        Format.TEXT_MAP, {"elastic-apm-traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    )

    assert span_context.trace_parent.version == 0
    assert span_context.trace_parent.trace_id == "0af7651916cd43dd8448eb211c80319c"
    assert span_context.trace_parent.span_id == "b7ad6b7169203331"


def test_tracer_extract_binary(tracer):
    with pytest.raises(opentracing.UnsupportedFormatException):
        tracer.extract(Format.BINARY, b"foo")


def test_tracer_extract_corrupted(tracer):
    with pytest.raises(opentracing.SpanContextCorruptedException):
        tracer.extract(Format.HTTP_HEADERS, {"nothing-to": "see-here"})


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        pytest.param({"use_elastic_traceparent_header": True}, id="use_elastic_traceparent_header-True"),
        pytest.param({"use_elastic_traceparent_header": False}, id="use_elastic_traceparent_header-False"),
    ],
    indirect=True,
)
def test_tracer_inject_http(tracer):
    span_context = OTSpanContext(
        trace_parent=TraceParent.from_string("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")
    )
    carrier = {}
    tracer.inject(span_context, Format.HTTP_HEADERS, carrier)
    assert carrier[constants.TRACEPARENT_HEADER_NAME] == b"00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    if tracer._agent.config.use_elastic_traceparent_header:
        assert carrier[constants.TRACEPARENT_LEGACY_HEADER_NAME] == carrier[constants.TRACEPARENT_HEADER_NAME]


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        pytest.param({"use_elastic_traceparent_header": True}, id="use_elastic_traceparent_header-True"),
        pytest.param({"use_elastic_traceparent_header": False}, id="use_elastic_traceparent_header-False"),
    ],
    indirect=True,
)
def test_tracer_inject_map(tracer):
    span_context = OTSpanContext(
        trace_parent=TraceParent.from_string("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")
    )
    carrier = {}
    tracer.inject(span_context, Format.TEXT_MAP, carrier)
    assert carrier[constants.TRACEPARENT_HEADER_NAME] == b"00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    if tracer._agent.config.use_elastic_traceparent_header:
        assert carrier[constants.TRACEPARENT_LEGACY_HEADER_NAME] == carrier[constants.TRACEPARENT_HEADER_NAME]


def test_tracer_inject_binary(tracer):
    span_context = OTSpanContext(
        trace_parent=TraceParent.from_string("00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01")
    )
    with pytest.raises(opentracing.UnsupportedFormatException):
        tracer.inject(span_context, Format.BINARY, {})
