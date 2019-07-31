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

import decimal
import logging
import time
from collections import defaultdict

import pytest
from mock import Mock

import elasticapm
from elasticapm.conf import Config
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.traces import Tracer, capture_span, execution_context


@pytest.fixture()
def tracer():
    frames = [
        {
            "function": "something_expensive",
            "abs_path": "/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/views.py",
            "lineno": 52,
            "module": "tests.contrib.django.testapp.views",
            "filename": "tests/contrib/django/testapp/views.py",
        },
        {
            "function": "_resolve_lookup",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py",
            "lineno": 789,
            "module": "django.template.base",
            "filename": "django/template/base.py",
        },
        {
            "function": "resolve",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py",
            "lineno": 735,
            "module": "django.template.base",
            "filename": "django/template/base.py",
        },
        {
            "function": "resolve",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py",
            "lineno": 585,
            "module": "django.template.base",
            "filename": "django/template/base.py",
        },
        {
            "lineno": 4,
            "filename": u"/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/templates/list_fish.html",
        },
        {
            "function": "render",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/defaulttags.py",
            "lineno": 4,
            "module": "django.template.defaulttags",
            "filename": "django/template/defaulttags.py",
        },
        {
            "function": "render_node",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/debug.py",
            "lineno": 78,
            "module": "django.template.debug",
            "filename": "django/template/debug.py",
        },
        {
            "function": "render",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py",
            "lineno": 840,
            "module": "django.template.base",
            "filename": "django/template/base.py",
        },
        {
            "function": "instrumented_test_render",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/utils.py",
            "lineno": 85,
            "module": "django.test.utils",
            "filename": "django/test/utils.py",
        },
        {
            "function": "render",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py",
            "lineno": 140,
            "module": "django.template.base",
            "filename": "django/template/base.py",
        },
        {
            "function": "rendered_content",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py",
            "lineno": 82,
            "module": "django.template.response",
            "filename": "django/template/response.py",
        },
        {
            "function": "render",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py",
            "lineno": 105,
            "module": "django.template.response",
            "filename": "django/template/response.py",
        },
        {
            "function": "get_response",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/core/handlers/base.py",
            "lineno": 137,
            "module": "django.core.handlers.base",
            "filename": "django/core/handlers/base.py",
        },
        {
            "function": "__call__",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py",
            "lineno": 109,
            "module": "django.test.client",
            "filename": "django/test/client.py",
        },
        {
            "function": "request",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py",
            "lineno": 426,
            "module": "django.test.client",
            "filename": "django/test/client.py",
        },
        {
            "function": "get",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py",
            "lineno": 280,
            "module": "django.test.client",
            "filename": "django/test/client.py",
        },
        {
            "function": "get",
            "abs_path": "/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py",
            "lineno": 473,
            "module": "django.test.client",
            "filename": "django/test/client.py",
        },
        {
            "function": "test_template_name_as_view",
            "abs_path": "/var/parent-elasticapm/elasticapm/tests/contrib/django/django_tests.py",
            "lineno": 710,
            "module": "tests.contrib.django.django_tests",
            "filename": "tests/contrib/django/django_tests.py",
        },
    ]

    events = defaultdict(list)

    def queue(event_type, event, flush=False):
        events[event_type].append(event)

    store = Tracer(lambda: frames, lambda frames: frames, queue, Config(), None)
    store.events = events
    return store


def test_leaf_tracing(tracer):
    tracer.begin_transaction("transaction.test")

    with capture_span("root", "custom"):
        with capture_span("child1-leaf", "custom", leaf=True):

            # These two spans should not show up
            with capture_span("ignored-child1", "custom", leaf=True):
                time.sleep(0.01)

            with capture_span("ignored-child2", "custom", leaf=False):
                time.sleep(0.01)

    tracer.end_transaction(None, "transaction")

    spans = tracer.events[SPAN]

    assert len(spans) == 2

    signatures = {"root", "child1-leaf"}
    assert {t["name"] for t in spans} == signatures


def test_get_transaction():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    t = requests_store.begin_transaction("test")
    assert t == execution_context.get_transaction()


def test_get_transaction_clear():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    t = requests_store.begin_transaction("test")
    assert t == execution_context.get_transaction(clear=True)
    assert execution_context.get_transaction() is None


def test_label_transaction():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    transaction = requests_store.begin_transaction("test")
    elasticapm.label(foo="bar")
    transaction.label(baz="bazzinga")
    requests_store.end_transaction(200, "test")

    assert transaction.labels == {"foo": "bar", "baz": "bazzinga"}
    transaction_dict = transaction.to_dict()
    assert transaction_dict["context"]["tags"] == {"foo": "bar", "baz": "bazzinga"}


def test_label_while_no_transaction(caplog):
    with caplog.at_level(logging.WARNING, "elasticapm.errors"):
        elasticapm.label(foo="bar")
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert "foo" in record.args


def test_label_with_allowed_non_string_value():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    t = requests_store.begin_transaction("test")
    elasticapm.label(foo=1, bar=True, baz=1.1, bazzinga=decimal.Decimal("1.1"))
    requests_store.end_transaction(200, "test")
    assert t.labels == {"foo": 1, "bar": True, "baz": 1.1, "bazzinga": decimal.Decimal("1.1")}


def test_label_with_not_allowed_non_string_value():
    class SomeType(object):
        def __str__(self):
            return "ok"

        def __unicode__(self):
            return u"ok"

    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    t = requests_store.begin_transaction("test")
    elasticapm.label(foo=SomeType())
    requests_store.end_transaction(200, "test")
    assert t.labels == {"foo": "ok"}


def test_labels_merge(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.label(foo=1, bar="baz")
    elasticapm.label(bar=3, boo="biz")
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["tags"] == {"foo": 1, "bar": 3, "boo": "biz"}


def test_labels_dedot(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.label(**{"d.o.t": "dot"})
    elasticapm.label(**{"s*t*a*r": "star"})
    elasticapm.label(**{'q"u"o"t"e': "quote"})

    elasticapm_client.end_transaction("test_name", 200)

    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["tags"] == {"d_o_t": "dot", "s_t_a_r": "star", "q_u_o_t_e": "quote"}


### TESTING DEPRECATED TAGGING START ###


def test_tagging_is_deprecated(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(DeprecationWarning, match="Call to deprecated function tag. Use elasticapm.label instead"):
        elasticapm.tag(foo="bar")
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["tags"] == {"foo": "bar"}


def test_tag_transaction():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, Config(), None)
    transaction = requests_store.begin_transaction("test")
    elasticapm.tag(foo="bar")
    transaction.tag(baz="bazzinga")
    requests_store.end_transaction(200, "test")

    assert transaction.labels == {"foo": "bar", "baz": "bazzinga"}
    transaction_dict = transaction.to_dict()
    assert transaction_dict["context"]["tags"] == {"foo": "bar", "baz": "bazzinga"}


def test_tag_while_no_transaction(caplog):
    with caplog.at_level(logging.WARNING, "elasticapm.errors"):
        elasticapm.tag(foo="bar")
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert "foo" in record.args


def test_tag_with_non_string_value():
    requests_store = Tracer(lambda: [], lambda: [], lambda *args: None, config=Config(), agent=None)
    t = requests_store.begin_transaction("test")
    elasticapm.tag(foo=1)
    requests_store.end_transaction(200, "test")
    assert t.labels == {"foo": "1"}


def test_tags_merge(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.tag(foo=1, bar="baz")
    elasticapm.tag(bar=3, boo="biz")
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["tags"] == {"foo": "1", "bar": "3", "boo": "biz"}


def test_tags_dedot(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.tag(**{"d.o.t": "dot"})
    elasticapm.tag(**{"s*t*a*r": "star"})
    elasticapm.tag(**{'q"u"o"t"e': "quote"})

    elasticapm_client.end_transaction("test_name", 200)

    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["tags"] == {"d_o_t": "dot", "s_t_a_r": "star", "q_u_o_t_e": "quote"}


### TESTING DEPRECATED TAGGING START ###


def test_dedot_is_not_run_when_unsampled(elasticapm_client):
    for sampled in (True, False):
        t = elasticapm_client.begin_transaction("test")
        t.is_sampled = sampled
        elasticapm.set_context(lambda: {"a.b": "b"})
        elasticapm_client.end_transaction("x", "OK")
    sampled_transaction, unsampled_transaction = transactions = elasticapm_client.events[TRANSACTION]
    assert "a_b" in sampled_transaction["context"]["custom"]
    assert "context" not in unsampled_transaction


def test_set_transaction_name(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm_client.end_transaction("test_name", 200)

    elasticapm_client.begin_transaction("test")

    elasticapm.set_transaction_name("another_name")

    elasticapm_client.end_transaction("test_name", 200)

    transactions = elasticapm_client.events[TRANSACTION]
    assert transactions[0]["name"] == "test_name"
    assert transactions[1]["name"] == "another_name"


def test_set_transaction_custom_data(elasticapm_client):
    elasticapm_client.begin_transaction("test")

    elasticapm.set_custom_context({"foo": "bar"})

    elasticapm_client.end_transaction("foo", 200)
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["custom"] == {"foo": "bar"}


def test_set_transaction_custom_data_merge(elasticapm_client):
    elasticapm_client.begin_transaction("test")

    elasticapm.set_custom_context({"foo": "bar", "bar": "baz"})
    elasticapm.set_custom_context({"bar": "bie", "boo": "biz"})

    elasticapm_client.end_transaction("foo", 200)
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["custom"] == {"foo": "bar", "bar": "bie", "boo": "biz"}


def test_set_user_context(elasticapm_client):
    elasticapm_client.begin_transaction("test")

    elasticapm.set_user_context(username="foo", email="foo@example.com", user_id=42)

    elasticapm_client.end_transaction("foo", 200)
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["user"] == {"username": "foo", "email": "foo@example.com", "id": 42}


def test_set_user_context_merge(elasticapm_client):
    elasticapm_client.begin_transaction("test")

    elasticapm.set_user_context(username="foo", email="bar@example.com")
    elasticapm.set_user_context(email="foo@example.com", user_id=42)

    elasticapm_client.end_transaction("foo", 200)
    transactions = elasticapm_client.events[TRANSACTION]

    assert transactions[0]["context"]["user"] == {"username": "foo", "email": "foo@example.com", "id": 42}


def test_dedot_context_keys(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.set_context({"d.o.t": "d_o_t", "s*t*a*r": "s_t_a_r", "q*u*o*t*e": "q_u_o_t_e"})
    elasticapm_client.end_transaction("foo", 200)
    transaction = elasticapm_client.events[TRANSACTION][0]
    assert transaction["context"]["custom"] == {"s_t_a_r": "s_t_a_r", "q_u_o_t_e": "q_u_o_t_e", "d_o_t": "d_o_t"}


def test_transaction_name_none_is_converted_to_empty_string(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    transaction = elasticapm_client.end_transaction(None, 200)
    assert transaction.name == ""


def test_transaction_without_name_result(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    transaction = elasticapm_client.end_transaction()
    assert transaction.name == ""


def test_dotted_span_type_conversion(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with capture_span("foo", "type"):
        with capture_span("bar", "type.subtype"):
            with capture_span("baz", "type.subtype.action"):
                with capture_span("bazzinga", "type.subtype.action.more"):
                    pass
    elasticapm_client.end_transaction("test", "OK")
    spans = elasticapm_client.events[SPAN]

    assert spans[0]["name"] == "bazzinga"
    assert spans[0]["type"] == "type"
    assert spans[0]["subtype"] == "subtype"
    assert spans[0]["action"] == "action"

    assert spans[1]["name"] == "baz"
    assert spans[1]["type"] == "type"
    assert spans[1]["subtype"] == "subtype"
    assert spans[1]["action"] == "action"

    assert spans[2]["name"] == "bar"
    assert spans[2]["type"] == "type"
    assert spans[2]["subtype"] == "subtype"
    assert spans[2]["action"] is None

    assert spans[3]["name"] == "foo"
    assert spans[3]["type"] == "type"
    assert spans[3]["subtype"] is None
    assert spans[3]["action"] is None


def test_span_labelling(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with elasticapm.capture_span("test", labels={"foo": "bar", "ba.z": "baz.zinga"}) as span:
        span.tag(lorem="ipsum")
    elasticapm_client.end_transaction("test", "OK")
    span = elasticapm_client.events[SPAN][0]
    assert span["context"]["tags"] == {"foo": "bar", "ba_z": "baz.zinga", "lorem": "ipsum"}


def test_span_tagging_raises_deprecation_warning(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(DeprecationWarning, match="The tags argument to capture_span is deprecated"):
        with elasticapm.capture_span("test", tags={"foo": "bar", "ba.z": "baz.zinga"}) as span:
            span.tag(lorem="ipsum")
    elasticapm_client.end_transaction("test", "OK")
