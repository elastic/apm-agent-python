import pytest  # isort:skip

opentracing = pytest.importorskip("opentracing")  # isort:skip

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
