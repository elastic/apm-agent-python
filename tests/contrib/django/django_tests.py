# -*- coding: utf-8 -*-
import pytest  # isort:skip
django = pytest.importorskip("django")  # isort:skip

import logging
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.handlers.wsgi import WSGIRequest
from django.core.management import call_command
from django.core.signals import got_request_exception
from django.db import DatabaseError
from django.http import QueryDict
from django.http.cookie import SimpleCookie
from django.template import TemplateSyntaxError
from django.test.client import Client as _TestClient
from django.test.client import ClientHandler as _TestClientHandler
from django.test.utils import override_settings

import mock

from elasticapm.base import Client
from elasticapm.contrib.django.client import client, get_client
from elasticapm.contrib.django.handlers import LoggingHandler
from elasticapm.contrib.django.middleware.wsgi import ElasticAPM
from elasticapm.traces import Transaction
from elasticapm.utils import compat
from elasticapm.utils.lru import LRUCache
from tests.contrib.django.testapp.views import IgnoredException
from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse


try:
    from celery.tests.utils import with_eager_tasks
    has_with_eager_tasks = True
except ImportError:
    from elasticapm.utils.compat import noop_decorator as with_eager_tasks
    has_with_eager_tasks = False


class MockClientHandler(_TestClientHandler):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return super(MockClientHandler, self).__call__(environ)


class MockMiddleware(ElasticAPM):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return list(super(MockMiddleware, self).__call__(environ, start_response))


def test_proxy_responds_as_client():
    assert get_client() == client


def test_basic(django_elasticapm_client):
    config = {
        'APP_ID': 'key',
        'ORGANIZATION_ID': 'org',
        'SECRET_TOKEN': '99'
    }
    event_count = len(django_elasticapm_client.events)
    with override_settings(ELASTIC_APM=config):
        django_elasticapm_client.capture('Message', message='foo')
        assert len(django_elasticapm_client.events) == event_count + 1
        django_elasticapm_client.events.pop(0)


def test_basic_django(django_elasticapm_client):
    django_elasticapm_client.capture('Message', message='foo')
    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    log = event['log']
    assert 'message' in log

    assert log['message'] == 'foo'
    assert log['level'] == 'error'
    assert log['param_message'] == 'foo'


def test_signal_integration(django_elasticapm_client):
    try:
        int('hello')
    except ValueError:
        got_request_exception.send(sender=None, request=None)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'exception' in event
    exc = event['exception']
    assert exc['type'] == 'ValueError'
    assert exc['message'] == u"ValueError: invalid literal for int() with base 10: 'hello'"
    assert event['culprit'] == 'tests.contrib.django.django_tests.test_signal_integration'


def test_view_exception(django_elasticapm_client, client):
    with pytest.raises(Exception):
        client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'exception' in event
    exc = event['exception']
    assert exc['type'] == 'Exception'
    assert exc['message'] == 'Exception: view exception'
    assert event['culprit'] == 'tests.contrib.django.testapp.views.raise_exc'


def test_view_exception_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = False
    with override_settings(DEBUG=True):
        with pytest.raises(Exception):
            client.get(reverse('elasticapm-raise-exc'))
    assert len(django_elasticapm_client.events) == 0


def test_view_exception_elasticapm_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = True
    with override_settings(DEBUG=True):
        with pytest.raises(Exception): client.get(reverse('elasticapm-raise-exc'))
    assert len(django_elasticapm_client.events) == 1


@pytest.mark.django_db
def test_user_info(django_elasticapm_client, client):
    user = User(username='admin', email='admin@example.com')
    user.set_password('admin')
    user.save()

    with pytest.raises(Exception):
        client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'user' in event['context']
    user_info = event['context']['user']
    assert 'is_authenticated' in user_info
    assert not user_info['is_authenticated']
    assert user_info['username'] == ''
    assert 'email' not in user_info

    assert client.login(username='admin', password='admin')

    with pytest.raises(Exception):
        client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'user' in event['context']
    user_info = event['context']['user']
    assert 'is_authenticated' in user_info
    assert user_info['is_authenticated']
    assert 'username' in user_info
    assert user_info['username'] == 'admin'
    assert 'email' in user_info
    assert user_info['email'] == 'admin@example.com'


@pytest.mark.django_db
def test_user_info_raises_database_error(django_elasticapm_client, client):
    user = User(username='admin', email='admin@example.com')
    user.set_password('admin')
    user.save()

    assert client.login(username='admin', password='admin')

    with mock.patch("django.contrib.auth.models.User.is_authenticated") as is_authenticated:
        is_authenticated.side_effect = DatabaseError("Test Exception")
        with pytest.raises(Exception):
            client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'user' in event['context']
    user_info = event['context']['user']
    assert user_info == {}


@pytest.mark.django_db
def test_user_info_with_custom_user(django_elasticapm_client, client):
    with override_settings(AUTH_USER_MODEL='testapp.MyUser'):
        from django.contrib.auth import get_user_model
        MyUser = get_user_model()
        user = MyUser(my_username='admin')
        user.set_password('admin')
        user.save()
        assert client.login(username='admin', password='admin')
        with pytest.raises(Exception):
            client.get(reverse('elasticapm-raise-exc'))

        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]
        assert 'user' in event['context']
        user_info = event['context']['user']
        assert 'is_authenticated' in user_info
        assert user_info['is_authenticated']
        assert 'username' in user_info
        assert user_info['username'] == 'admin'
        assert 'email' not in user_info


@pytest.mark.skipif(django.VERSION > (1, 9),
                    reason='MIDDLEWARE_CLASSES removed in Django 2.0')
def test_user_info_with_non_django_auth(django_elasticapm_client, client):
    with override_settings(INSTALLED_APPS=[
        app for app in settings.INSTALLED_APPS
        if app != 'django.contrib.auth'
    ]) and override_settings(MIDDLEWARE_CLASSES=[
        m for m in settings.MIDDLEWARE_CLASSES
        if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
    ]):
        with pytest.raises(Exception):
            resp = client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['user'] == {}


@pytest.mark.skipif(django.VERSION < (1, 10),
                    reason='MIDDLEWARE new in Django 1.10')
def test_user_info_with_non_django_auth_django_2(django_elasticapm_client, client):
    with override_settings(INSTALLED_APPS=[
        app for app in settings.INSTALLED_APPS
        if app != 'django.contrib.auth'
    ]) and override_settings(MIDDLEWARE_CLASSES=None, MIDDLEWARE=[
        m for m in settings.MIDDLEWARE
        if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
    ]):
        with pytest.raises(Exception):
            resp = client.get(reverse('elasticapm-raise-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['user'] == {}


@pytest.mark.skipif(django.VERSION > (1, 9),
                    reason='MIDDLEWARE_CLASSES removed in Django 2.0')
def test_user_info_without_auth_middleware(django_elasticapm_client, client):
    with override_settings(MIDDLEWARE_CLASSES=[
        m for m in settings.MIDDLEWARE_CLASSES
        if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
    ]):
        with pytest.raises(Exception):
            client.get(reverse('elasticapm-raise-exc'))
    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['user'] == {}


@pytest.mark.skipif(django.VERSION < (1, 10),
                    reason='MIDDLEWARE new in Django 1.10')
def test_user_info_without_auth_middleware_django_2(django_elasticapm_client, client):
    with override_settings(MIDDLEWARE_CLASSES=None, MIDDLEWARE=[
        m for m in settings.MIDDLEWARE
        if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
    ]):
        with pytest.raises(Exception):
            client.get(reverse('elasticapm-raise-exc'))
    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['user'] == {}


def test_request_middleware_exception(django_elasticapm_client, client):
    with override_settings(**middleware_setting(django.VERSION,
                                            ['tests.contrib.django.testapp.middleware.BrokenRequestMiddleware'])):
        with pytest.raises(ImportError):
            client.get(reverse('elasticapm-raise-exc'))

        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert 'exception' in event
        exc = event['exception']
        assert exc['type'] == 'ImportError'
        assert exc['message'] == 'ImportError: request'
        assert event['culprit'] == 'tests.contrib.django.testapp.middleware.process_request'


def test_response_middlware_exception(django_elasticapm_client, client):
    if django.VERSION[:2] < (1, 3):
        return
    with override_settings(**middleware_setting(django.VERSION,
                                            ['tests.contrib.django.testapp.middleware.BrokenResponseMiddleware'])):
        with pytest.raises(ImportError):
            client.get(reverse('elasticapm-no-error'))

        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert 'exception' in event
        exc = event['exception']
        assert exc['type'] == 'ImportError'
        assert exc['message'] == 'ImportError: response'
        assert event['culprit'] == 'tests.contrib.django.testapp.middleware.process_response'


def test_broken_500_handler_with_middleware(django_elasticapm_client, client):
    with override_settings(BREAK_THAT_500=True):
        client.handler = MockMiddleware(MockClientHandler())

        with override_settings(**middleware_setting(django.VERSION, [])):
            with pytest.raises(Exception):
                client.get(reverse('elasticapm-raise-exc'))

        assert len(django_elasticapm_client.events) == 2
        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert 'exception' in event
        exc = event['exception']
        assert exc['type'] == 'Exception'
        assert exc['message'] == 'Exception: view exception'
        assert event['culprit'] == 'tests.contrib.django.testapp.views.raise_exc'

        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert 'exception' in event
        exc = event['exception']
        assert exc['type'] == 'ValueError'
        assert exc['message'] == 'ValueError: handler500'
        assert event['culprit'] == 'tests.contrib.django.testapp.urls.handler500'

def test_view_middleware_exception(django_elasticapm_client, client):
    with override_settings(**middleware_setting(django.VERSION,
                                            ['tests.contrib.django.testapp.middleware.BrokenViewMiddleware'])):
        with pytest.raises(ImportError):
            client.get(reverse('elasticapm-raise-exc'))

        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert 'exception' in event
        exc = event['exception']
        assert exc['type'] == 'ImportError'
        assert exc['message'] == 'ImportError: view'
        assert event['culprit'] == 'tests.contrib.django.testapp.middleware.process_view'


def test_exclude_modules_view(django_elasticapm_client, client):
    django_elasticapm_client.config.exclude_paths = ['tests.views.decorated_raise_exc']
    with pytest.raises(Exception):
        client.get(reverse('elasticapm-raise-exc-decor'))

    assert len(django_elasticapm_client.events) == 1, django_elasticapm_client.events
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert event['culprit'] == 'tests.contrib.django.testapp.views.raise_exc'


def test_include_modules(django_elasticapm_client, client):
    django_elasticapm_client.config.include_paths = ['django.shortcuts.get_object_or_404']

    with pytest.raises(Exception):
        client.get(reverse('elasticapm-django-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert event['culprit'] == 'django.shortcuts.get_object_or_404'


def test_ignored_exception_is_ignored(django_elasticapm_client, client):
    with pytest.raises(IgnoredException):
        client.get(reverse('elasticapm-ignored-exception'))
    assert len(django_elasticapm_client.events) == 0


def test_template_name_as_view(django_elasticapm_client, client):
    # TODO this test passes only with TEMPLATE_DEBUG=True
    with override_settings(
        TEMPLATE_DEBUG=True,
        TEMPLATES=[
            {
                'BACKEND': settings.TEMPLATES[0]['BACKEND'],
                'DIRS': settings.TEMPLATES[0]['DIRS'],
                'OPTIONS': {
                    'context_processors': settings.TEMPLATES[0]['OPTIONS']['context_processors'],
                    'loaders': settings.TEMPLATES[0]['OPTIONS']['loaders'],
                    'debug': True,
                },
            },
        ]
    ):
        with pytest.raises(TemplateSyntaxError):
            client.get(reverse('elasticapm-template-exc'))

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert event['culprit'] == 'error.html'

    assert event['template']['context_line'] == '{% invalid template tag %}\n'


@pytest.mark.skipif(compat.PY3, reason='see Python bug #10805')
def test_record_none_exc_info(django_elasticapm_client):
    # sys.exc_info can return (None, None, None) if no exception is being
    # handled anywhere on the stack. See:
    #  http://docs.python.org/library/sys.html#sys.exc_info
    record = logging.LogRecord(
        'foo',
        logging.INFO,
        pathname=None,
        lineno=None,
        msg='test',
        args=(),
        exc_info=(None, None, None),
    )
    handler = LoggingHandler()
    handler.emit(record)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert event['log']['param_message'] == 'test'
    assert event['log']['logger_name'] == 'foo'
    assert event['log']['level'] == 'info'
    assert 'exception' not in event


def test_404_middleware(django_elasticapm_client, client):
    with override_settings(**middleware_setting(django.VERSION,
                                            ['elasticapm.contrib.django.middleware.Catch404Middleware'])):
        resp = client.get('/non-existant-page')
        assert resp.status_code == 404

        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]

        assert event['log']['level'] == 'info'
        assert event['log']['logger_name'] == 'http404'

        assert 'request' in event['context']
        request = event['context']['request']
        assert request['url']['raw'] == u'http://testserver/non-existant-page'
        assert request['method'] == 'GET'
        assert request['url']['search'] == ''
        assert request['body'] == None


def test_404_middleware_with_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = False
    with override_settings(
            DEBUG=True,
            **middleware_setting(django.VERSION, [
                'elasticapm.contrib.django.middleware.Catch404Middleware'
            ])
    ):
        resp = client.get('/non-existant-page')
        assert resp.status_code == 404
        assert len(django_elasticapm_client.events) == 0


def test_response_error_id_middleware(django_elasticapm_client, client):
    with override_settings(**middleware_setting(django.VERSION, [
            'elasticapm.contrib.django.middleware.ErrorIdMiddleware',
            'elasticapm.contrib.django.middleware.Catch404Middleware'])):
        resp = client.get('/non-existant-page')
        assert resp.status_code == 404
        headers = dict(resp.items())
        assert 'X-ElasticAPM-ErrorId' in headers
        assert len(django_elasticapm_client.events) == 1
        event = django_elasticapm_client.events.pop(0)['errors'][0]
        assert event['id'] == headers['X-ElasticAPM-ErrorId']


def test_get_client(django_elasticapm_client):
    assert get_client() == get_client()
    assert get_client('elasticapm.base.Client').__class__ == Client


def test_raw_post_data_partial_read(django_elasticapm_client):
    v = compat.b('{"foo": "bar"}')
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(v + compat.b('\r\n\r\n')),
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'application/json',
        'CONTENT_LENGTH': len(v),
        'ACCEPT': 'application/json',
    })
    request.read(1)

    django_elasticapm_client.capture('Message', message='foo', request=request)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['method'] == 'POST'
    assert request['body'] == '<unavailable>'


def test_post_data(django_elasticapm_client):
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(),
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'application/json',
        'ACCEPT': 'application/json',
    })
    request.POST = QueryDict("x=1&y=2")
    django_elasticapm_client.capture('Message', message='foo', request=request)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['method'] == 'POST'
    assert request['body'] == {'x': '1', 'y': '2'}


def test_post_raw_data(django_elasticapm_client):
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(compat.b('foobar')),
        'wsgi.url_scheme': 'http',
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'application/json',
        'ACCEPT': 'application/json',
        'CONTENT_LENGTH': '6',
    })
    django_elasticapm_client.capture('Message', message='foo', request=request)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['method'] == 'POST'
    assert request['body'] == compat.b('foobar')


@pytest.mark.skipif(django.VERSION < (1, 9),
                    reason='get-raw-uri-not-available')
def test_disallowed_hosts_error_django_19(django_elasticapm_client):
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(),
        'wsgi.url_scheme': 'http',
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'application/json',
        'ACCEPT': 'application/json',
    })
    with override_settings(ALLOWED_HOSTS=['example.com']):
        # this should not raise a DisallowedHost exception
        django_elasticapm_client.capture('Message', message='foo', request=request)
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['request']['url']['raw'] == 'http://testserver/'


@pytest.mark.skipif(django.VERSION >= (1, 9),
                    reason='get-raw-uri-available')
def test_disallowed_hosts_error_django_18(django_elasticapm_client):
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(),
        'wsgi.url_scheme': 'http',
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'application/json',
        'ACCEPT': 'application/json',
    })
    with override_settings(ALLOWED_HOSTS=['example.com']):
        # this should not raise a DisallowedHost exception
        django_elasticapm_client.capture('Message', message='foo', request=request)
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert event['context']['request']['url'] == {'raw': 'DisallowedHost'}


def test_request_capture(django_elasticapm_client):
    request = WSGIRequest(environ={
        'wsgi.input': compat.BytesIO(),
        'REQUEST_METHOD': 'POST',
        'SERVER_NAME': 'testserver',
        'SERVER_PORT': '80',
        'CONTENT_TYPE': 'text/html',
        'ACCEPT': 'text/html',
    })
    request.read(1)

    django_elasticapm_client.capture('Message', message='foo', request=request)

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['method'] == 'POST'
    assert request['body'] == '<unavailable>'
    assert 'headers' in request
    headers = request['headers']
    assert 'content-type' in headers, headers.keys()
    assert headers['content-type'] == 'text/html'
    env = request['env']
    assert 'SERVER_NAME' in env, env.keys()
    assert env['SERVER_NAME'] == 'testserver'
    assert 'SERVER_PORT' in env, env.keys()
    assert env['SERVER_PORT'] == '80'


def test_transaction_request_response_data(django_elasticapm_client, client):
    client.cookies = SimpleCookie({'foo': 'bar'})
    django_elasticapm_client.instrumentation_store.get_all()
    with override_settings(**middleware_setting(
            django.VERSION, ['elasticapm.contrib.django.middleware.TracingMiddleware']
    )):
        client.get(reverse('elasticapm-no-error'))
    assert len(django_elasticapm_client.instrumentation_store) == 1
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction['result'] == 'HTTP 2xx'
    assert 'request' in transaction['context']
    request = transaction['context']['request']
    assert request['method'] == 'GET'
    assert 'headers' in request
    headers = request['headers']
    assert headers['cookie'] == ' foo=bar'
    env = request['env']
    assert 'SERVER_NAME' in env, env.keys()
    assert env['SERVER_NAME'] == 'testserver'
    assert 'SERVER_PORT' in env, env.keys()
    assert env['SERVER_PORT'] == '80'

    assert 'response' in transaction['context']
    response = transaction['context']['response']
    assert response['status_code'] == 200
    assert response['headers']['my-header'] == 'foo'


def test_transaction_metrics(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store
    with override_settings(**middleware_setting(
            django.VERSION, ['elasticapm.contrib.django.middleware.TracingMiddleware']
    )):
        assert len(django_elasticapm_client.instrumentation_store) == 0
        client.get(reverse('elasticapm-no-error'))
        assert len(django_elasticapm_client.instrumentation_store) == 1

        transactions = django_elasticapm_client.instrumentation_store.get_all()

        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction['duration'] > 0
        assert transaction['result'] == 'HTTP 2xx'
        assert transaction['name'] == 'GET tests.contrib.django.testapp.views.no_error'


def test_request_metrics_301_append_slash(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store

    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True

    from elasticapm.contrib.django.middleware import TracingMiddleware
    TracingMiddleware._elasticapm_instrumented = False

    with override_settings(
        APPEND_SLASH=True,
        **middleware_setting(django.VERSION, [
            'elasticapm.contrib.django.middleware.TracingMiddleware',
            'django.middleware.common.CommonMiddleware',
        ])
    ):
        client.get(reverse('elasticapm-no-error-slash')[:-1])
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] in (
        # django <= 1.8
        'GET django.middleware.common.CommonMiddleware.process_request',
        # django 1.9+
        'GET django.middleware.common.CommonMiddleware.process_response',
    )
    assert transactions[0]['result'] == 'HTTP 3xx'


def test_request_metrics_301_prepend_www(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store

    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True

    from elasticapm.contrib.django.middleware import TracingMiddleware
    TracingMiddleware._elasticapm_instrumented = False

    with override_settings(
        PREPEND_WWW=True,
        **middleware_setting(django.VERSION, [
            'elasticapm.contrib.django.middleware.TracingMiddleware',
            'django.middleware.common.CommonMiddleware',
        ])
    ):
        client.get(reverse('elasticapm-no-error'))
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] == 'GET django.middleware.common.CommonMiddleware.process_request'
    assert transactions[0]['result'] == 'HTTP 3xx'


@pytest.mark.django_db
def test_request_metrics_contrib_redirect(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store

    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True
    from elasticapm.contrib.django.middleware import TracingMiddleware
    TracingMiddleware._elasticapm_instrumented = False

    s = Site.objects.get(pk=1)
    Redirect.objects.create(site=s, old_path='/redirect/me/', new_path='/here/')

    with override_settings(
        **middleware_setting(django.VERSION, [
            'elasticapm.contrib.django.middleware.TracingMiddleware',
            'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
        ])
    ):
        response = client.get('/redirect/me/')

    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] == 'GET django.contrib.redirects.middleware.RedirectFallbackMiddleware.process_response'
    assert transactions[0]['result'] == 'HTTP 3xx'


def test_request_metrics_name_override(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store
    with override_settings(
        **middleware_setting(django.VERSION, [
            'elasticapm.contrib.django.middleware.TracingMiddleware',
            'tests.contrib.django.testapp.middleware.MetricsNameOverrideMiddleware',
        ])
    ):
        client.get(reverse('elasticapm-no-error'))
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] == 'GET foobar'


def test_request_metrics_404_resolve_error(django_elasticapm_client, client):
    django_elasticapm_client.instrumentation_store.get_all()  # clear the store
    with override_settings(
        **middleware_setting(django.VERSION, ['elasticapm.contrib.django.middleware.TracingMiddleware'])
    ):
        client.get('/i-dont-exist/')
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['name'] == ''


def test_get_app_info(django_elasticapm_client):
    app_info = django_elasticapm_client.get_app_info()
    assert django.get_version() == app_info['framework']['version']
    assert app_info['framework']['name'] == 'django'
    assert django_elasticapm_client.config.framework_name == 'django'


@mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
@pytest.mark.parametrize('django_sending_elasticapm_client', [{'filter_exception_types': [
        'KeyError', 'tests.contrib.django.fake1.FakeException'
    ]}], indirect=True)
def test_filter_no_match(send_encoded, django_sending_elasticapm_client):
    try:
        raise ValueError('foo')
    except:
        django_sending_elasticapm_client.capture('Exception')

    assert send_encoded.call_count == 1


@mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
@pytest.mark.parametrize('django_sending_elasticapm_client', [{'filter_exception_types': [
        'KeyError', 'tests.contrib.django.fake1.FakeException'
    ]}], indirect=True)
def test_filter_matches_type(send_encoded, django_sending_elasticapm_client):
    try:
        raise KeyError('foo')
    except:
        django_sending_elasticapm_client.capture('Exception')

    assert send_encoded.call_count == 0


@mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
@pytest.mark.parametrize('django_sending_elasticapm_client', [{'filter_exception_types': [
        'KeyError', 'tests.contrib.django.fake1.FakeException'
    ]}], indirect=True)
def test_filter_matches_type_but_not_module(send_encoded, django_sending_elasticapm_client):
    try:
        from tests.contrib.django.fake2 import FakeException
        raise FakeException('foo')
    except:
        django_sending_elasticapm_client.capture('Exception')

    assert send_encoded.call_count == 1


@mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
@pytest.mark.parametrize('django_sending_elasticapm_client', [{'filter_exception_types': [
        'KeyError', 'tests.contrib.django.fake1.FakeException'
    ]}], indirect=True)
def test_filter_matches_type_and_module(send_encoded, django_sending_elasticapm_client):
    try:
        from tests.contrib.django.fake1 import FakeException
        raise FakeException('foo')
    except:
        django_sending_elasticapm_client.capture('Exception')

    assert send_encoded.call_count == 0


@mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
@pytest.mark.parametrize('django_sending_elasticapm_client', [{'filter_exception_types': [
        'KeyError', 'tests.contrib.django.fake1.FakeException'
    ]}], indirect=True)
def test_filter_matches_module_only(send_encoded, django_sending_elasticapm_client):
    try:
        from tests.contrib.django.fake1 import OtherFakeException
        raise OtherFakeException('foo')
    except OtherFakeException:
        django_sending_elasticapm_client.capture('Exception')

    assert send_encoded.call_count == 1


def test_django_logging_request_kwarg(django_elasticapm_client):
    handler = LoggingHandler()

    logger = logging.getLogger(__name__)
    logger.handlers = []
    logger.addHandler(handler)

    logger.error('This is a test error', extra={
        'request': WSGIRequest(environ={
            'wsgi.input': compat.StringIO(),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'ACCEPT': 'application/json',
        })
    })

    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'request' in event['context']
    request = event['context']['request']
    assert request['method'] == 'POST'


def test_django_logging_middleware(django_elasticapm_client, client):
    handler = LoggingHandler()

    logger = logging.getLogger('logmiddleware')
    logger.handlers = []
    logger.addHandler(handler)

    with override_settings(**middleware_setting(django.VERSION,
                                                ['elasticapm.contrib.django.middleware.LogMiddleware'])):
        client.get(reverse('elasticapm-logging'))
    assert len(django_elasticapm_client.events) == 1
    event = django_elasticapm_client.events.pop(0)['errors'][0]
    assert 'request' in event['context']
    assert event['context']['request']['url']['pathname'] == reverse('elasticapm-logging')


def client_get(client, url):
    return client.get(url)


def test_stacktraces_have_templates(client, django_elasticapm_client):
    # Clear the LRU frame cache
    Transaction._lrucache = LRUCache(maxsize=5000)

    # only Django 1.9+ have the necessary information stored on Node/Template
    # instances when TEMPLATE_DEBUG = False

    TEMPLATE_DEBUG = django.VERSION < (1, 9)

    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        TEMPLATES_copy = deepcopy(settings.TEMPLATES)
        TEMPLATES_copy[0]['OPTIONS']['debug'] = TEMPLATE_DEBUG
        with override_settings(
            TEMPLATE_DEBUG=TEMPLATE_DEBUG,
            TEMPLATES=TEMPLATES_copy,
            **middleware_setting(django.VERSION, [
                'elasticapm.contrib.django.middleware.TracingMiddleware'
            ])
        ):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction['result'] == 'HTTP 2xx'
    traces = transaction['traces']
    assert len(traces) == 2, [t['name'] for t in traces]

    expected_names = {'list_users.html', 'something_expensive'}

    assert {t['name'] for t in traces} == expected_names

    assert traces[0]['name'] == 'something_expensive'

    # Find the template
    for frame in traces[0]['stacktrace']:
        if frame['lineno'] == 4 and frame['filename'].endswith(
                'django/testapp/templates/list_users.html'
        ):
            break
    else:
        assert False is True, "Template was not found"


def test_stacktrace_filtered_for_elasticapm(client, django_elasticapm_client):
    # Clear the LRU frame cache
    Transaction._lrucache = LRUCache(maxsize=5000)

    with mock.patch(
            "elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert transactions[0]['result'] == 'HTTP 2xx'
    traces = transactions[0]['traces']

    expected_signatures = ['transaction', 'list_users.html',
                           'something_expensive']

    assert traces[1]['name'] == 'list_users.html'

    # Top frame should be inside django rendering
    assert traces[1]['stacktrace'][0]['module'].startswith('django.template')


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_template_render(benchmark, client, django_elasticapm_client):
    responses = []
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            benchmark(lambda: responses.append(
                client_get(client, reverse("render-heavy-template"))
            ))
    for resp in responses:
        assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()

    # If the test falls right at the change from one minute to another
    # this will have two items.
    assert len(transactions) == len(responses)
    for transaction in transactions:
        assert len(transaction['traces']) == 2
        assert transaction['result'] == 'HTTP 2xx'


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_template_render_no_middleware(benchmark, client, django_elasticapm_client):
    responses = []
    with mock.patch(
            "elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        benchmark(lambda: responses.append(
            client_get(client, reverse("render-heavy-template"))
        ))
    for resp in responses:
        assert resp.status_code == 200

    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 0


@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
@pytest.mark.django_db(transaction=True)
def test_perf_database_render(benchmark, client, django_elasticapm_client):
    responses = []
    django_elasticapm_client.instrumentation_store.get_all()

    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            benchmark(lambda: responses.append(
                client_get(client, reverse("render-user-template"))
            ))
        for resp in responses:
            assert resp.status_code == 200

        transactions = django_elasticapm_client.instrumentation_store.get_all()

        assert len(transactions) == len(responses)
        for transaction in transactions:
            assert len(transaction['traces']) in (102, 103)


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_database_render_no_instrumentation(benchmark, django_elasticapm_client):
    django_elasticapm_client.instrumentation_store.get_all()
    responses = []
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        client = _TestClient()
        benchmark(lambda: responses.append(
            client_get(client, reverse("render-user-template"))
        ))

        for resp in responses:
            assert resp.status_code == 200

        transactions = django_elasticapm_client.instrumentation_store.get_all()
        assert len(transactions) == 0


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_transaction_with_collection(benchmark, django_elasticapm_client):
    django_elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        django_elasticapm_client.events = []

        client = _TestClient()

        with override_settings(**middleware_setting(django.VERSION,
                                                    ['elasticapm.contrib.django.middleware.TracingMiddleware'])):
            for i in range(10):
                resp = client_get(client, reverse("render-user-template"))
                assert resp.status_code == 200

        assert len(django_elasticapm_client.events) == 0

        # Force collection on next request
        should_collect.return_value = True

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert result.status_code is 200
        assert len(django_elasticapm_client.events) > 0


@pytest.mark.django_db
@pytest.mark.parametrize('django_elasticapm_client', [{'_wait_to_first_send': 100}], indirect=True)
def test_perf_transaction_without_middleware(benchmark, django_elasticapm_client):
    django_elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        client = _TestClient()
        django_elasticapm_client.events = []
        for i in range(10):
            resp = client_get(client, reverse("render-user-template"))
            assert resp.status_code == 200

        assert len(django_elasticapm_client.events) == 0

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert len(django_elasticapm_client.events) == 0


@pytest.mark.skipif(django.VERSION > (1, 7),
                    reason='argparse raises CommandError in this case')
@mock.patch('elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv')
def test_subcommand_not_set(argv_mock):
    stdout = compat.StringIO()
    argv_mock.return_value = ['manage.py', 'elasticapm']
    call_command('elasticapm', stdout=stdout)
    output = stdout.getvalue()
    assert 'No command specified' in output


@mock.patch('elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv')
def test_subcommand_not_known(argv_mock):
    stdout = compat.StringIO()
    argv_mock.return_value = ['manage.py', 'elasticapm']
    call_command('elasticapm', 'foo', stdout=stdout)
    output = stdout.getvalue()
    assert 'No such command "foo"' in output


def test_settings_missing():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={}):
        call_command('elasticapm', 'check', stdout=stdout)
    output = stdout.getvalue()
    assert 'Configuration errors detected' in output
    assert 'APP_NAME not set' in output
    assert 'SECRET_TOKEN not set' in output


def test_middleware_not_set():
    stdout = compat.StringIO()
    with override_settings(**middleware_setting(django.VERSION, ())):
        call_command('elasticapm', 'check', stdout=stdout)
    output = stdout.getvalue()
    assert 'Tracing middleware not configured!' in output


def test_middleware_not_first():
    stdout = compat.StringIO()
    with override_settings(**middleware_setting(django.VERSION, (
        'foo',
        'elasticapm.contrib.django.middleware.TracingMiddleware'
    ))):
        call_command('elasticapm', 'check', stdout=stdout)
    output = stdout.getvalue()
    assert 'not at the first position' in output


@mock.patch('elasticapm.transport.http_urllib3.urllib3.PoolManager.urlopen')
def test_test_exception(urlopen_mock):
    stdout = compat.StringIO()
    resp = mock.Mock(status=200, getheader=lambda h: 'http://example.com')
    urlopen_mock.return_value = resp
    with override_settings(**middleware_setting(django.VERSION, [
        'foo',
        'elasticapm.contrib.django.middleware.TracingMiddleware'
    ])):
        call_command('elasticapm', 'test', stdout=stdout, stderr=stdout)
    output = stdout.getvalue()
    assert 'Success! We tracked the error successfully!' in output


def test_tracing_middleware_uses_test_client(client, django_elasticapm_client):
    with override_settings(**middleware_setting(django.VERSION, [
        'elasticapm.contrib.django.middleware.TracingMiddleware'
    ])):
        client.get('/')
    transactions = django_elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 1
    assert transactions[0]['context']['request']['url']['pathname'] == '/'
