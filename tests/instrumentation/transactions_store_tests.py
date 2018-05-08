import logging
import time

import pytest
from mock import Mock

import elasticapm
from elasticapm.traces import TransactionsStore, capture_span, get_transaction


@pytest.fixture()
def transaction_store():
    mock_get_frames = Mock()

    frames = [{'function': 'something_expensive',
               'abs_path': '/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/views.py',
               'lineno': 52, 'module': 'tests.contrib.django.testapp.views',
               'filename': 'tests/contrib/django/testapp/views.py'},
              {'function': '_resolve_lookup',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
               'lineno': 789, 'module': 'django.template.base',
               'filename': 'django/template/base.py'},
              {'function': 'resolve',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
               'lineno': 735, 'module': 'django.template.base',
               'filename': 'django/template/base.py'},
              {'function': 'resolve',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
               'lineno': 585, 'module': 'django.template.base',
               'filename': 'django/template/base.py'}, {'lineno': 4,
                                                        'filename': u'/var/parent-elasticapm/elasticapm/tests/contrib/django/testapp/templates/list_fish.html'},
              {'function': 'render',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/defaulttags.py',
               'lineno': 4, 'module': 'django.template.defaulttags',
               'filename': 'django/template/defaulttags.py'},
              {'function': 'render_node',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/debug.py',
               'lineno': 78, 'module': 'django.template.debug',
               'filename': 'django/template/debug.py'},
              {'function': 'render',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
               'lineno': 840, 'module': 'django.template.base',
               'filename': 'django/template/base.py'},
              {'function': 'instrumented_test_render',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/utils.py',
               'lineno': 85, 'module': 'django.test.utils',
               'filename': 'django/test/utils.py'}, {'function': 'render',
                                                     'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/base.py',
                                                     'lineno': 140,
                                                     'module': 'django.template.base',
                                                     'filename': 'django/template/base.py'},
              {'function': 'rendered_content',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py',
               'lineno': 82, 'module': 'django.template.response',
               'filename': 'django/template/response.py'},
              {'function': 'render',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/template/response.py',
               'lineno': 105, 'module': 'django.template.response',
               'filename': 'django/template/response.py'},
              {'function': 'get_response',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/core/handlers/base.py',
               'lineno': 137, 'module': 'django.core.handlers.base',
               'filename': 'django/core/handlers/base.py'},
              {'function': '__call__',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
               'lineno': 109, 'module': 'django.test.client',
               'filename': 'django/test/client.py'}, {'function': 'request',
                                                      'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                                                      'lineno': 426,
                                                      'module': 'django.test.client',
                                                      'filename': 'django/test/client.py'},
              {'function': 'get',
               'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
               'lineno': 280, 'module': 'django.test.client',
               'filename': 'django/test/client.py'}, {'function': 'get',
                                                      'abs_path': '/home/ron/.virtualenvs/elasticapm/local/lib/python2.7/site-packages/django/test/client.py',
                                                      'lineno': 473,
                                                      'module': 'django.test.client',
                                                      'filename': 'django/test/client.py'},
              {'function': 'test_template_name_as_view',
               'abs_path': '/var/parent-elasticapm/elasticapm/tests/contrib/django/django_tests.py',
               'lineno': 710, 'module': 'tests.contrib.django.django_tests',
               'filename': 'tests/contrib/django/django_tests.py'}]

    mock_get_frames.return_value = frames
    return TransactionsStore(mock_get_frames, 99999)


def test_leaf_tracing(transaction_store):
    transaction_store.begin_transaction("transaction.test")

    with capture_span("root", "custom"):
        with capture_span("child1-leaf", "custom", leaf=True):

            # These two spans should not show up
            with capture_span("ignored-child1", "custom", leaf=True):
                time.sleep(0.01)

            with capture_span("ignored-child2", "custom", leaf=False):
                time.sleep(0.01)

    transaction_store.end_transaction(None, "transaction")

    transactions = transaction_store.get_all()
    spans = transactions[0]['spans']

    assert len(spans) == 2

    signatures = {'root', 'child1-leaf'}
    assert {t['name'] for t in spans} == signatures


def test_get_transaction():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    assert t == get_transaction()


def test_get_transaction_clear():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    assert t == get_transaction(clear=True)
    assert get_transaction() is None


def test_should_collect_time():
    requests_store = TransactionsStore(lambda: [], collect_frequency=5)
    requests_store._last_collect -= 6

    assert requests_store.should_collect()


def test_should_not_collect_time():
    requests_store = TransactionsStore(lambda: [], collect_frequency=5)
    requests_store._last_collect -= 3

    assert not requests_store.should_collect()


def test_should_collect_count():
    requests_store = TransactionsStore(lambda: [], collect_frequency=5, max_queue_size=5)
    requests_store._transactions = 6 * [1]
    requests_store._last_collect -= 3

    assert requests_store.should_collect()


def test_should_not_collect_count():
    requests_store = TransactionsStore(lambda: [], collect_frequency=5, max_queue_size=5)
    requests_store._transactions = 4 * [1]

    assert not requests_store.should_collect()


def test_tag_transaction():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    elasticapm.tag(foo='bar')
    requests_store.end_transaction(200, 'test')

    assert t.tags == {'foo': 'bar'}
    transaction_dict = t.to_dict()
    assert transaction_dict['context']['tags'] == {'foo': 'bar'}


def test_tag_while_no_transaction(caplog):
    elasticapm.tag(foo='bar')
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert 'foo' in record.args


def test_tag_with_non_string_value():
    requests_store = TransactionsStore(lambda: [], 99999)
    t = requests_store.begin_transaction("test")
    elasticapm.tag(foo=1)
    requests_store.end_transaction(200, 'test')
    assert t.tags == {'foo': '1'}


def test_tags_merge(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    elasticapm.tag(foo=1, bar='baz')
    elasticapm.tag(bar=3, boo='biz')
    elasticapm_client.end_transaction('test', 'OK')
    transactions = elasticapm_client.instrumentation_store.get_all()

    assert transactions[0]['context']['tags'] == {'foo': '1', 'bar': '3', 'boo': 'biz'}


def test_set_transaction_name(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    elasticapm_client.end_transaction('test_name', 200)

    elasticapm_client.begin_transaction('test')

    elasticapm.set_transaction_name('another_name')

    elasticapm_client.end_transaction('test_name', 200)

    transactions = elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] == 'test_name'
    assert transactions[1]['name'] == 'another_name'


def test_set_transaction_custom_data(elasticapm_client):
    elasticapm_client.begin_transaction('test')

    elasticapm.set_custom_context({'foo': 'bar'})

    elasticapm_client.end_transaction('foo', 200)
    transactions = elasticapm_client.instrumentation_store.get_all()

    assert transactions[0]['context']['custom'] == {'foo': 'bar'}


def test_set_transaction_custom_data_merge(elasticapm_client):
    elasticapm_client.begin_transaction('test')

    elasticapm.set_custom_context({'foo': 'bar', 'bar': 'baz'})
    elasticapm.set_custom_context({'bar': 'bie', 'boo': 'biz'})

    elasticapm_client.end_transaction('foo', 200)
    transactions = elasticapm_client.instrumentation_store.get_all()

    assert transactions[0]['context']['custom'] == {'foo': 'bar', 'bar': 'bie', 'boo': 'biz'}


def test_set_user_context(elasticapm_client):
    elasticapm_client.begin_transaction('test')

    elasticapm.set_user_context(username='foo', email='foo@example.com', user_id=42)

    elasticapm_client.end_transaction('foo', 200)
    transactions = elasticapm_client.instrumentation_store.get_all()

    assert transactions[0]['context']['user'] == {'username': 'foo', 'email': 'foo@example.com', 'id': 42}


def test_set_user_context_merge(elasticapm_client):
    elasticapm_client.begin_transaction('test')

    elasticapm.set_user_context(username='foo', email='bar@example.com')
    elasticapm.set_user_context(email='foo@example.com', user_id=42)

    elasticapm_client.end_transaction('foo', 200)
    transactions = elasticapm_client.instrumentation_store.get_all()

    assert transactions[0]['context']['user'] == {'username': 'foo', 'email': 'foo@example.com', 'id': 42}


def test_transaction_name_none_is_converted_to_empty_string(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    transaction = elasticapm_client.end_transaction(None, 200)
    assert transaction.name == ''


def test_transaction_without_name_result(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    transaction = elasticapm_client.end_transaction()
    assert transaction.name == ''
