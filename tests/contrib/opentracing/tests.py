import pytest  # isort:skip

opentracing = pytest.importorskip("opentracing")  # isort:skip

import sys

from elasticapm.conf import constants
from elasticapm.contrib.opentracing import Tracer

pytestmark = pytest.mark.opentracing


@pytest.fixture()
def tracer(elasticapm_client):
    yield Tracer(client_instance=elasticapm_client)


def test_ot_transaction_started(tracer):
    with tracer.start_active_span("test") as ot_scope:
        ot_scope.span.set_tag("result", "OK")
    client = tracer._agent
    transaction = client.events[constants.TRANSACTION][0]
    assert transaction["type"] == "opentracing"
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


def test_error_log_automatic_in_span_context_manager(tracer):
    scope = tracer.start_active_span("transaction")
    with pytest.raises(ValueError):
        with scope.span:
            raise ValueError("oops")

    client = tracer._agent
    error = client.events[constants.ERROR][0]

    assert error["exception"]["message"] == "ValueError: oops"
