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
from django.core.urlresolvers import reverse
from django.db import DatabaseError
from django.http import QueryDict
from django.template import TemplateSyntaxError
from django.test import TestCase
from django.test.client import Client as _TestClient
from django.test.client import ClientHandler as _TestClientHandler
from django.test.utils import override_settings

import mock
import pytest

from elasticapm import instrumentation
from elasticapm.base import Client
from elasticapm.contrib.django import DjangoClient
from elasticapm.contrib.django.handlers import LoggingHandler
from elasticapm.contrib.django.middleware.wsgi import ElasticAPM
from elasticapm.contrib.django.models import (client, get_client,
                                              get_client_config)
from elasticapm.traces import Transaction
from elasticapm.utils import six
from elasticapm.utils.lru import LRUCache
from tests.contrib.django.testapp.views import IgnoredException

try:
    from celery.tests.utils import with_eager_tasks
    has_with_eager_tasks = True
except ImportError:
    from elasticapm.utils.compat import noop_decorator as with_eager_tasks
    has_with_eager_tasks = False


settings.ELASTICAPM = {'CLIENT': 'tests.contrib.django.django_tests.TempStoreClient'}


class MockClientHandler(_TestClientHandler):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return super(MockClientHandler, self).__call__(environ)


class MockMiddleware(ElasticAPM):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return list(super(MockMiddleware, self).__call__(environ, start_response))


class TempStoreClient(DjangoClient):
    def __init__(self, *args, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(*args, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)


class ClientProxyTest(TestCase):
    def test_proxy_responds_as_client(self):
        self.assertEquals(get_client(), client)

    def test_basic(self):
        config = {
            'APP_ID': 'key',
            'ORGANIZATION_ID': 'org',
            'SECRET_TOKEN': '99'
        }
        config.update(settings.ELASTICAPM)
        event_count = len(client.events)
        with self.settings(ELASTICAPM=config):
            client.capture('Message', message='foo')
            self.assertEquals(len(client.events), event_count + 1)
            client.events.pop(0)


class DjangoClientTest(TestCase):

    urls = 'tests.contrib.django.testapp.urls'

    def setUp(self):
        self.elasticapm_client = get_client()
        self.elasticapm_client.events = []
        instrumentation.control.instrument()

    def test_basic(self):
        self.elasticapm_client.capture('Message', message='foo')
        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        log = event['log']
        self.assertTrue('message' in log)

        self.assertEquals(log['message'], 'foo')
        self.assertEquals(log['level'], 'error')
        self.assertEquals(log['param_message'], 'foo')

    def test_signal_integration(self):
        try:
            int('hello')
        except:
            got_request_exception.send(sender=self.__class__, request=None)
        else:
            self.fail('Expected an exception.')

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], u"ValueError: invalid literal for int() with base 10: 'hello'")
        self.assertEquals(event['culprit'], 'tests.contrib.django.django_tests.test_signal_integration')

    def test_view_exception(self):
        self.assertRaises(Exception, self.client.get, reverse('elasticapm-raise-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'Exception')
        self.assertEquals(exc['message'], 'Exception: view exception')
        self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')

    def test_view_exception_debug(self):
        with self.settings(DEBUG=True):
            self.assertRaises(
                Exception,
                self.client.get, reverse('elasticapm-raise-exc')
            )
        self.assertEquals(len(self.elasticapm_client.events), 0)

    def test_view_exception_elasticapm_debug(self):
        with self.settings(
            DEBUG=True,
            ELASTICAPM={
                'DEBUG': True,
                'CLIENT': 'tests.contrib.django.django_tests.TempStoreClient'
            },
        ):
            self.assertRaises(
                Exception,
                self.client.get, reverse('elasticapm-raise-exc')
            )
        self.assertEquals(len(self.elasticapm_client.events), 1)

    def test_user_info(self):
        user = User(username='admin', email='admin@example.com')
        user.set_password('admin')
        user.save()

        self.assertRaises(Exception, self.client.get, reverse('elasticapm-raise-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        self.assertTrue('user' in event['context'])
        user_info = event['context']['user']
        self.assertTrue('is_authenticated' in user_info)
        self.assertFalse(user_info['is_authenticated'])
        assert user_info['username'] == ''
        self.assertFalse('email' in user_info)

        self.assertTrue(self.client.login(username='admin', password='admin'))

        self.assertRaises(Exception, self.client.get, reverse('elasticapm-raise-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        self.assertTrue('user' in event['context'])
        user_info = event['context']['user']
        self.assertTrue('is_authenticated' in user_info)
        self.assertTrue(user_info['is_authenticated'])
        self.assertTrue('username' in user_info)
        self.assertEquals(user_info['username'], 'admin')
        self.assertTrue('email' in user_info)
        self.assertEquals(user_info['email'], 'admin@example.com')

    def test_user_info_raises_database_error(self):
        user = User(username='admin', email='admin@example.com')
        user.set_password('admin')
        user.save()

        self.assertTrue(
            self.client.login(username='admin', password='admin'))

        with mock.patch("django.contrib.auth.models.User.is_authenticated") as is_authenticated:
            is_authenticated.side_effect = DatabaseError("Test Exception")
            self.assertRaises(Exception, self.client.get,
                              reverse('elasticapm-raise-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        self.assertTrue('user' in event['context'])
        user_info = event['context']['user']
        self.assertEquals(user_info, {})

    @pytest.mark.skipif(django.VERSION < (1, 5),
                        reason='Custom user model was introduced with Django 1.5')
    def test_user_info_with_custom_user(self):
        with self.settings(AUTH_USER_MODEL='testapp.MyUser'):
            from django.contrib.auth import get_user_model
            MyUser = get_user_model()
            user = MyUser(my_username='admin')
            user.set_password('admin')
            user.save()
            self.assertTrue(self.client.login(username='admin', password='admin'))
            self.assertRaises(Exception, self.client.get, reverse('elasticapm-raise-exc'))

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]
            self.assertTrue('user' in event['context'])
            user_info = event['context']['user']
            self.assertTrue('is_authenticated' in user_info)
            self.assertTrue(user_info['is_authenticated'])
            self.assertTrue('username' in user_info)
            self.assertEquals(user_info['username'], 'admin')
            self.assertFalse('email' in user_info)

    def test_user_info_with_non_django_auth(self):
        with self.settings(INSTALLED_APPS=[
            app for app in settings.INSTALLED_APPS
            if app != 'django.contrib.auth'
        ]) and self.settings(MIDDLEWARE_CLASSES=[
            m for m in settings.MIDDLEWARE_CLASSES
            if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
        ]):
            with pytest.raises(Exception):
                resp = self.client.get(reverse('elasticapm-raise-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        assert event['context']['user'] == {}

    def test_user_info_without_auth_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=[
            m for m in settings.MIDDLEWARE_CLASSES
            if m != 'django.contrib.auth.middleware.AuthenticationMiddleware'
        ]):
            self.assertRaises(Exception,
                              self.client.get,
                              reverse('elasticapm-raise-exc'))
        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        assert event['context']['user'] == {}

    def test_request_middleware_exception(self):
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenRequestMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('elasticapm-raise-exc'))

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['message'], 'ImportError: request')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_request')

    def test_response_middlware_exception(self):
        if django.VERSION[:2] < (1, 3):
            return
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenResponseMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('elasticapm-no-error'))

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['message'], 'ImportError: response')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_response')

    def test_broken_500_handler_with_middleware(self):
        with self.settings(BREAK_THAT_500=True):
            client = _TestClient(REMOTE_ADDR='127.0.0.1')
            client.handler = MockMiddleware(MockClientHandler())

            self.assertRaises(Exception, client.get, reverse('elasticapm-raise-exc'))

            self.assertEquals(len(self.elasticapm_client.events), 2)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'Exception')
            self.assertEquals(exc['message'], 'Exception: view exception')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')

            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ValueError')
            self.assertEquals(exc['message'], 'ValueError: handler500')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.urls.handler500')

    def test_view_middleware_exception(self):
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenViewMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('elasticapm-raise-exc'))

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['message'], 'ImportError: view')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_view')

    def test_exclude_modules_view(self):
        exclude_paths = self.elasticapm_client.exclude_paths
        self.elasticapm_client.exclude_paths = ['tests.views.decorated_raise_exc']
        self.assertRaises(Exception, self.client.get, reverse('elasticapm-raise-exc-decor'))

        self.assertEquals(len(self.elasticapm_client.events), 1, self.elasticapm_client.events)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')
        self.elasticapm_client.exclude_paths = exclude_paths

    def test_include_modules(self):
        include_paths = self.elasticapm_client.include_paths
        self.elasticapm_client.include_paths = ['django.shortcuts.get_object_or_404']

        self.assertRaises(Exception, self.client.get, reverse('elasticapm-django-exc'))

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertEquals(event['culprit'], 'django.shortcuts.get_object_or_404')
        self.elasticapm_client.include_paths = include_paths

    def test_ignored_exception_is_ignored(self):
        with pytest.raises(IgnoredException):
            self.client.get(reverse('elasticapm-ignored-exception'))
        self.assertEquals(len(self.elasticapm_client.events), 0)

    def test_template_name_as_view(self):
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
            self.assertRaises(
                TemplateSyntaxError,
                self.client.get, reverse('elasticapm-template-exc')
            )

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertEquals(event['culprit'], 'error.html')

        self.assertEquals(
            event['template']['context_line'],
            '{% invalid template tag %}\n'
        )

    @pytest.mark.skipif(six.PY3, reason='see Python bug #10805')
    def test_record_none_exc_info(self):
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

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertEquals(event['log']['param_message'], 'test')
        self.assertEquals(event['log']['logger_name'], 'foo')
        self.assertEquals(event['log']['level'], 'info')
        assert 'exception' not in event

    def test_404_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=['elasticapm.contrib.django.middleware.Catch404Middleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertEquals(event['log']['level'], 'info')
            self.assertEquals(event['log']['logger_name'], 'http404')

            self.assertTrue('request' in event['context'])
            request = event['context']['request']
            self.assertEquals(request['url']['raw'], u'http://testserver/non-existant-page')
            self.assertEquals(request['method'], 'GET')
            self.assertEquals(request['url']['search'], '')
            self.assertEquals(request['body'], None)

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_404_new_style_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=None, MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.Catch404Middleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)

            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]

            self.assertEquals(event['log']['level'], 'info')
            self.assertEquals(event['log']['logger_name'], 'http404')

            self.assertTrue('request' in event['context'])
            request = event['context']['request']
            self.assertEquals(request['url']['raw'], u'http://testserver/non-existant-page')
            self.assertEquals(request['method'], 'GET')
            self.assertEquals(request['url']['search'], '')
            self.assertEquals(request['body'], None)

    def test_404_middleware_with_debug(self):
        with self.settings(
                MIDDLEWARE_CLASSES=[
                    'elasticapm.contrib.django.middleware.Catch404Middleware'
                ],
                DEBUG=True,
        ):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            self.assertEquals(len(self.elasticapm_client.events), 0)

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_404_new_style_middleware_with_debug(self):
        with self.settings(
                MIDDLEWARE_CLASSES=None,
                MIDDLEWARE=[
                    'elasticapm.contrib.django.middleware.Catch404Middleware'
                ],
                DEBUG=True,
        ):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            self.assertEquals(len(self.elasticapm_client.events), 0)

    def test_response_error_id_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.ErrorIdMiddleware',
                'elasticapm.contrib.django.middleware.Catch404Middleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            headers = dict(resp.items())
            self.assertTrue('X-ElasticAPM-ErrorId' in headers)
            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]
            self.assertEquals(event['id'], headers['X-ElasticAPM-ErrorId'])

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_response_error_id_middleware_new_style(self):
        with self.settings(MIDDLEWARE_CLASSES=None, MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.ErrorIdMiddleware',
                'elasticapm.contrib.django.middleware.Catch404Middleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            headers = dict(resp.items())
            self.assertTrue('X-ElasticAPM-ErrorId' in headers)
            self.assertEquals(len(self.elasticapm_client.events), 1)
            event = self.elasticapm_client.events.pop(0)['errors'][0]
            self.assertEquals(event['id'], headers['X-ElasticAPM-ErrorId'])

    def test_get_client(self):
        self.assertEquals(get_client(), get_client())
        self.assertEquals(get_client('elasticapm.base.Client').__class__, Client)
        self.assertEquals(get_client(), self.elasticapm_client)

        self.assertEquals(get_client('%s.%s' % (self.elasticapm_client.__class__.__module__, self.elasticapm_client.__class__.__name__)), self.elasticapm_client)
        self.assertEquals(get_client(), self.elasticapm_client)

    # This test only applies to Django 1.3+
    def test_raw_post_data_partial_read(self):
        if django.VERSION[:2] < (1, 3):
            return
        v = six.b('{"foo": "bar"}')
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(v + six.b('\r\n\r\n')),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': len(v),
            'ACCEPT': 'application/json',
        })
        request.read(1)

        self.elasticapm_client.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['method'], 'POST')
        self.assertEquals(request['body'], '<unavailable>')

    def test_post_data(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'ACCEPT': 'application/json',
        })
        request.POST = QueryDict("x=1&y=2")
        self.elasticapm_client.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['method'], 'POST')
        self.assertEquals(request['body'], {'x': '1', 'y': '2'})

    def test_post_raw_data(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(six.b('foobar')),
            'wsgi.url_scheme': 'http',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'ACCEPT': 'application/json',
            'CONTENT_LENGTH': '6',
        })
        self.elasticapm_client.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['method'], 'POST')
        self.assertEquals(request['body'], six.b('foobar'))

    @pytest.mark.skipif(django.VERSION < (1, 9),
                        reason='get-raw-uri-not-available')
    def test_disallowed_hosts_error_django_19(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(),
            'wsgi.url_scheme': 'http',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'ACCEPT': 'application/json',
        })
        with self.settings(ALLOWED_HOSTS=['example.com']):
            # this should not raise a DisallowedHost exception
            self.elasticapm_client.capture('Message', message='foo', request=request)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        assert event['context']['request']['url']['raw'] == 'http://testserver/'

    @pytest.mark.skipif(django.VERSION >= (1, 9),
                        reason='get-raw-uri-available')
    def test_disallowed_hosts_error_django_18(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(),
            'wsgi.url_scheme': 'http',
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/json',
            'ACCEPT': 'application/json',
        })
        with self.settings(ALLOWED_HOSTS=['example.com']):
            # this should not raise a DisallowedHost exception
            self.elasticapm_client.capture('Message', message='foo', request=request)
        event = self.elasticapm_client.events.pop(0)['errors'][0]
        assert event['context']['request']['url'] == {'raw': 'DisallowedHost'}

    # This test only applies to Django 1.3+
    def test_request_capture(self):
        if django.VERSION[:2] < (1, 3):
            return
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'text/html',
            'ACCEPT': 'text/html',
        })
        request.read(1)

        self.elasticapm_client.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.elasticapm_client.events), 1)
        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['method'], 'POST')
        self.assertEquals(request['body'], '<unavailable>')
        self.assertTrue('headers' in request)
        headers = request['headers']
        self.assertTrue('content-type' in headers, headers.keys())
        self.assertEquals(headers['content-type'], 'text/html')
        env = request['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'testserver')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_transaction_metrics(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store
        with self.settings(MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware']):
            self.assertEqual(len(self.elasticapm_client.instrumentation_store), 0)
            self.client.get(reverse('elasticapm-no-error'))
            self.assertEqual(len(self.elasticapm_client.instrumentation_store), 1)

            transactions = self.elasticapm_client.instrumentation_store.get_all()

            assert len(transactions) == 1
            transaction = transactions[0]
            assert transaction['duration'] > 0
            assert transaction['result'] == '200'
            assert transaction['name'] == 'GET tests.contrib.django.testapp.views.no_error'

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_transaction_metrics_new_style_middleware(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store
        with self.settings(MIDDLEWARE_CLASSES=None, MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.TracingMiddleware']):
            self.assertEqual(len(self.elasticapm_client.instrumentation_store), 0)
            self.client.get(reverse('elasticapm-no-error'))
            self.assertEqual(len(self.elasticapm_client.instrumentation_store), 1)

            transactions = self.elasticapm_client.instrumentation_store.get_all()

            assert len(transactions) == 1
            transaction = transactions[0]
            assert transaction['duration'] > 0
            assert transaction['result'] == '200'
            assert transaction['name'] == 'GET tests.contrib.django.testapp.views.no_error'

    def test_request_metrics_301_append_slash(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            APPEND_SLASH=True,
        ):
            self.client.get(reverse('elasticapm-no-error-slash')[:-1])
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertIn(
            transactions[0]['name'], (
                # django <= 1.8
                'GET django.middleware.common.CommonMiddleware.process_request',
                # django 1.9+
                'GET django.middleware.common.CommonMiddleware.process_response',
            )
        )

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_request_metrics_301_append_slash_new_style_middleware(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=None,
            MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            APPEND_SLASH=True,
        ):
            self.client.get(reverse('elasticapm-no-error-slash')[:-1])
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertIn(
            transactions[0]['name'], (
                # django <= 1.8
                'GET django.middleware.common.CommonMiddleware.process_request',
                # django 1.9+
                'GET django.middleware.common.CommonMiddleware.process_response',
            )
        )

    def test_request_metrics_301_prepend_www(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            PREPEND_WWW=True,
        ):
            self.client.get(reverse('elasticapm-no-error'))
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            'GET django.middleware.common.CommonMiddleware.process_request'
        )

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_request_metrics_301_prepend_www_new_style_middleware(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=None,
            MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            PREPEND_WWW=True,
        ):
            self.client.get(reverse('elasticapm-no-error'))
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            'GET django.middleware.common.CommonMiddleware.process_request'
        )

    def test_request_metrics_contrib_redirect(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True
        from elasticapm.contrib.django.middleware import TracingMiddleware
        TracingMiddleware._elasticapm_instrumented = False

        s = Site.objects.get(pk=1)
        Redirect.objects.create(site=s, old_path='/redirect/me/', new_path='/here/')

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
            ],
        ):
            response = self.client.get('/redirect/me/')

        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            'GET django.contrib.redirects.middleware.RedirectFallbackMiddleware'
            '.process_response'
        )

    @pytest.mark.skipif(django.VERSION < (1, 10),
                        reason='new-style middlewares')
    def test_request_metrics_contrib_redirect_new_style_middleware(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True
        from elasticapm.contrib.django.middleware import TracingMiddleware
        TracingMiddleware._elasticapm_instrumented = False

        s = Site.objects.get(pk=1)
        Redirect.objects.create(site=s, old_path='/redirect/me/', new_path='/here/')

        with self.settings(
            MIDDLEWARE_CLASSES=None,
            MIDDLEWARE=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
            ],
        ):
            response = self.client.get('/redirect/me/')

        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            'GET django.contrib.redirects.middleware.RedirectFallbackMiddleware'
            '.process_response'
        )

    def test_ASYNC_config_raises_deprecation(self):
        config = {
            'ORGANIZATION_ID': '1',
            'APP_ID': '1',
            'SECRET_TOKEN': '1',
            'ASYNC': True,
        }
        with self.settings(ELASTICAPM=config):
            pytest.deprecated_call(get_client_config)

    def test_request_metrics_name_override(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store
        with self.settings(
            MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware',
                'tests.contrib.django.testapp.middleware.MetricsNameOverrideMiddleware',
            ]
        ):
            self.client.get(reverse('elasticapm-no-error'))
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            'GET foobar'
        )

    def test_request_metrics_404_resolve_error(self):
        self.elasticapm_client.instrumentation_store.get_all()  # clear the store
        with self.settings(
                MIDDLEWARE_CLASSES=[
                    'elasticapm.contrib.django.middleware.TracingMiddleware',
                ]
        ):
            self.client.get('/i-dont-exist/')
        transactions = self.elasticapm_client.instrumentation_store.get_all()
        self.assertEqual(
            transactions[0]['name'],
            ''
        )

    def test_get_app_info(self):
        client = get_client()
        app_info = client.get_app_info()
        assert django.get_version() == app_info['framework']['version']
        assert 'django' == app_info['framework']['name']


class DjangoClientNoTempTest(TestCase):
    def setUp(self):
        self.client = DjangoClient(
            servers=['http://example.com'],
            app_name='app',
            secret_token='secret',
            filter_exception_types=['KeyError', 'tests.contrib.django.fake1.FakeException']
        )

    @mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
    def test_filter_no_match(self, send_encoded):
        try:
            raise ValueError('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 1)

    @mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type(self, send_encoded):
        try:
            raise KeyError('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 0)

    @mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type_but_not_module(self, send_encoded):
        try:
            from tests.contrib.django.fake2 import FakeException
            raise FakeException('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 1)

    @mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type_and_module(self, send_encoded):
        try:
            from tests.contrib.django.fake1 import FakeException
            raise FakeException('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 0)

    @mock.patch('elasticapm.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_module_only(self, send_encoded):
        try:
            from tests.contrib.django.fake1 import OtherFakeException
            raise OtherFakeException('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 1)


class DjangoLoggingTest(TestCase):
    def setUp(self):
        self.logger = logging.getLogger(__name__)
        self.client = get_client()

    def test_request_kwarg(self):
        handler = LoggingHandler()

        logger = self.logger
        logger.handlers = []
        logger.addHandler(handler)

        logger.error('This is a test error', extra={
            'request': WSGIRequest(environ={
                'wsgi.input': six.StringIO(),
                'REQUEST_METHOD': 'POST',
                'SERVER_NAME': 'testserver',
                'SERVER_PORT': '80',
                'CONTENT_TYPE': 'application/json',
                'ACCEPT': 'application/json',
            })
        })

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['method'], 'POST')


def client_get(client, url):
    return client.get(url)


def test_stacktraces_have_templates():
    client = _TestClient()
    elasticapm_client = get_client()
    instrumentation.control.instrument()

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
            MIDDLEWARE_CLASSES=[
                'elasticapm.contrib.django.middleware.TracingMiddleware'
            ],
            TEMPLATE_DEBUG=TEMPLATE_DEBUG,
            TEMPLATES=TEMPLATES_copy
        ):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 1
    transaction = transactions[0]
    traces = transaction['traces']
    assert len(traces) == 3, [t['name'] for t in traces]

    expected_names = ['transaction', 'list_users.html',
                           'something_expensive']

    assert set([t['name'] for t in traces]) == set(expected_names)

    assert traces[0]['name'] == 'something_expensive'

    # Find the template
    for frame in traces[0]['stacktrace']:
        if frame['lineno'] == 4 and frame['filename'].endswith(
                'django/testapp/templates/list_users.html'
        ):
            break
    else:
        assert False is True, "Template was not found"


def test_stacktrace_filtered_for_elasticapm():
    client = _TestClient()
    elasticapm_client = get_client()
    instrumentation.control.instrument()

    # Clear the LRU frame cache
    Transaction._lrucache = LRUCache(maxsize=5000)

    with mock.patch(
            "elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(MIDDLEWARE_CLASSES=[
            'elasticapm.contrib.django.middleware.TracingMiddleware']):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = ['transaction', 'list_users.html',
                           'something_expensive']

    assert traces[1]['name'] == 'list_users.html'

    # Top frame should be inside django rendering
    assert traces[1]['stacktrace'][0]['module'].startswith('django.template')

def test_perf_template_render(benchmark):
    client = _TestClient()
    elasticapm_client = get_client()
    responses = []
    instrumentation.control.instrument()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(MIDDLEWARE_CLASSES=[
            'elasticapm.contrib.django.middleware.TracingMiddleware']):
            benchmark(lambda: responses.append(
                client_get(client, reverse("render-heavy-template"))
            ))
    for resp in responses:
        assert resp.status_code == 200

    transactions = elasticapm_client.instrumentation_store.get_all()

    # If the test falls right at the change from one minute to another
    # this will have two items.
    assert len(transactions) == len(responses)
    for transaction in transactions:
        assert len(transaction['traces']) == 3


def test_perf_template_render_no_middleware(benchmark):
    client = _TestClient()
    elasticapm_client = get_client()
    responses = []
    instrumentation.control.instrument()
    with mock.patch(
            "elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        benchmark(lambda: responses.append(
            client_get(client, reverse("render-heavy-template"))
        ))
    for resp in responses:
        assert resp.status_code == 200

    transactions = elasticapm_client.instrumentation_store.get_all()
    assert len(transactions) == 0


@pytest.mark.django_db(transaction=True)
def test_perf_database_render(benchmark):
    client = _TestClient()

    elasticapm_client = get_client()
    instrumentation.control.instrument()
    responses = []
    elasticapm_client.instrumentation_store.get_all()

    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        with override_settings(MIDDLEWARE_CLASSES=[
            'elasticapm.contrib.django.middleware.TracingMiddleware']):
            benchmark(lambda: responses.append(
                client_get(client, reverse("render-user-template"))
            ))
        for resp in responses:
            assert resp.status_code == 200

        transactions = elasticapm_client.instrumentation_store.get_all()

        assert len(transactions) == len(responses)
        for transaction in transactions:
            assert len(transaction['traces']) in (103, 104)


@pytest.mark.django_db
def test_perf_database_render_no_instrumentation(benchmark):
    elasticapm_client = get_client()
    elasticapm_client.instrumentation_store.get_all()
    responses = []
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False

        client = _TestClient()
        benchmark(lambda: responses.append(
            client_get(client, reverse("render-user-template"))
        ))

        for resp in responses:
            assert resp.status_code == 200

        transactions = elasticapm_client.instrumentation_store.get_all()
        assert len(transactions) == 0


@pytest.mark.django_db
def test_perf_transaction_with_collection(benchmark):
    elasticapm_client = get_client()
    elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        elasticapm_client.events = []

        client = _TestClient()

        with override_settings(MIDDLEWARE_CLASSES=[
            'elasticapm.contrib.django.middleware.TracingMiddleware']):

            for i in range(10):
                resp = client_get(client, reverse("render-user-template"))
                assert resp.status_code == 200

        assert len(elasticapm_client.events) == 0

        # Force collection on next request
        should_collect.return_value = True

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert result.status_code is 200
        assert len(elasticapm_client.events) > 0


@pytest.mark.django_db
def test_perf_transaction_without_middleware(benchmark):
    elasticapm_client = get_client()
    elasticapm_client.instrumentation_store.get_all()
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        client = _TestClient()
        elasticapm_client.events = []
        for i in range(10):
            resp = client_get(client, reverse("render-user-template"))
            assert resp.status_code == 200

        assert len(elasticapm_client.events) == 0

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert len(elasticapm_client.events) == 0


class DjangoManagementCommandTest(TestCase):
    @pytest.mark.skipif(django.VERSION > (1, 7),
                        reason='argparse raises CommandError in this case')
    @mock.patch('elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv')
    def test_subcommand_not_set(self, argv_mock):
        stdout = six.StringIO()
        argv_mock.return_value = ['manage.py', 'elasticapm']
        call_command('elasticapm', stdout=stdout)
        output = stdout.getvalue()
        assert 'No command specified' in output

    @mock.patch('elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv')
    def test_subcommand_not_known(self, argv_mock):
        stdout = six.StringIO()
        argv_mock.return_value = ['manage.py', 'elasticapm']
        call_command('elasticapm', 'foo', stdout=stdout)
        output = stdout.getvalue()
        assert 'No such command "foo"' in output

    def test_settings_missing(self):
        stdout = six.StringIO()
        with self.settings(ELASTICAPM={}):
            call_command('elasticapm', 'check', stdout=stdout)
        output = stdout.getvalue()
        assert 'Configuration errors detected' in output
        assert 'APP_NAME not set' in output
        assert 'SECRET_TOKEN not set' in output

    def test_middleware_not_set(self):
        stdout = six.StringIO()
        with self.settings(MIDDLEWARE_CLASSES=()):
            call_command('elasticapm', 'check', stdout=stdout)
        output = stdout.getvalue()
        assert 'Tracing middleware not configured!' in output

    def test_middleware_not_first(self):
        stdout = six.StringIO()
        with self.settings(MIDDLEWARE_CLASSES=(
            'foo',
            'elasticapm.contrib.django.middleware.TracingMiddleware'
        )):
            call_command('elasticapm', 'check', stdout=stdout)
        output = stdout.getvalue()
        assert 'not at the first position' in output

    @mock.patch('elasticapm.transport.http_urllib3.urllib3.PoolManager.urlopen')
    def test_test_exception(self, urlopen_mock):
        stdout = six.StringIO()
        resp = mock.Mock(status=200, getheader=lambda h: 'http://example.com')
        urlopen_mock.return_value = resp
        with self.settings(MIDDLEWARE_CLASSES=(
                'foo',
                'elasticapm.contrib.django.middleware.TracingMiddleware'
        )):
            call_command('elasticapm', 'test', stdout=stdout, stderr=stdout)
        output = stdout.getvalue()
        assert 'http://example.com' in output
