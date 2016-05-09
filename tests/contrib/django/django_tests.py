# -*- coding: utf-8 -*-
import pytest  # isort:skip
django = pytest.importorskip("django")  # isort:skip

import datetime
import logging
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.handlers.wsgi import WSGIRequest
from django.core.signals import got_request_exception
from django.core.urlresolvers import reverse
from django.db import DatabaseError
from django.http import QueryDict
from django.template import TemplateSyntaxError
from django.test import TestCase
from django.test.client import Client as TestClient
from django.test.client import ClientHandler as TestClientHandler
from django.test.utils import override_settings

import mock
import pytest

from opbeat import instrumentation
from opbeat.base import Client
from opbeat.contrib.django import DjangoClient
from opbeat.contrib.django.celery import CeleryClient
from opbeat.contrib.django.handlers import OpbeatHandler
from opbeat.contrib.django.management.commands.opbeat import \
    Command as DjangoCommand
from opbeat.contrib.django.middleware.wsgi import Opbeat
from opbeat.contrib.django.models import client, get_client, get_client_config
from opbeat.traces import Transaction
from opbeat.utils import six
from opbeat.utils.lru import LRUCache

try:
    from celery.tests.utils import with_eager_tasks
    has_with_eager_tasks = True
except ImportError:
    from opbeat.utils.compat import noop_decorator as with_eager_tasks
    has_with_eager_tasks = False


settings.OPBEAT = {'CLIENT': 'tests.contrib.django.django_tests.TempStoreClient'}


class MockClientHandler(TestClientHandler):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return super(MockClientHandler, self).__call__(environ)


class MockOpbeatMiddleware(Opbeat):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return list(super(MockOpbeatMiddleware, self).__call__(environ, start_response))


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
        config.update(settings.OPBEAT)
        event_count = len(client.events)
        with self.settings(OPBEAT=config):
            client.capture('Message', message='foo')
            self.assertEquals(len(client.events), event_count + 1)
            client.events.pop(0)


class DjangoClientTest(TestCase):

    urls = 'tests.contrib.django.testapp.urls'

    def setUp(self):
        self.opbeat = get_client()
        self.opbeat.events = []
        instrumentation.control.instrument()

    def test_basic(self):
        self.opbeat.capture('Message', message='foo')
        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('message' in event)

        self.assertEquals(event['message'], 'foo')
        self.assertEquals(event['level'], 'error')
        self.assertEquals(event['param_message'], {'message':'foo','params':()})
        self.assertEquals(type(event['timestamp']), datetime.datetime)

    def test_signal_integration(self):
        try:
            int('hello')
        except:
            got_request_exception.send(sender=self.__class__, request=None)
        else:
            self.fail('Expected an exception.')

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], u"invalid literal for int() with base 10: 'hello'")
        self.assertEquals(event['level'], 'error')
        self.assertEquals(event['message'], u"ValueError: invalid literal for int() with base 10: 'hello'")
        self.assertEquals(event['culprit'], 'tests.contrib.django.django_tests.test_signal_integration')

    def test_view_exception(self):
        self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'Exception')
        self.assertEquals(exc['value'], 'view exception')
        self.assertEquals(event['level'], 'error')
        self.assertEquals(event['message'], 'Exception: view exception')
        self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')

    def test_view_exception_debug(self):
        with self.settings(DEBUG=True):
            self.assertRaises(
                Exception,
                self.client.get, reverse('opbeat-raise-exc')
            )
        self.assertEquals(len(self.opbeat.events), 0)

    def test_view_exception_opbeat_debug(self):
        with self.settings(
            DEBUG=True,
            OPBEAT={
                'DEBUG': True,
                'CLIENT': 'tests.contrib.django.django_tests.TempStoreClient'
            },
        ):
            self.assertRaises(
                Exception,
                self.client.get, reverse('opbeat-raise-exc')
            )
        self.assertEquals(len(self.opbeat.events), 1)

    def test_user_info(self):
        user = User(username='admin', email='admin@example.com')
        user.set_password('admin')
        user.save()

        self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('user' in event)
        user_info = event['user']
        self.assertTrue('is_authenticated' in user_info)
        self.assertFalse(user_info['is_authenticated'])
        self.assertFalse('username' in user_info)
        self.assertFalse('email' in user_info)

        self.assertTrue(self.client.login(username='admin', password='admin'))

        self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('user' in event)
        user_info = event['user']
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
                              reverse('opbeat-raise-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('user' in event)
        user_info = event['user']
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
            self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)
            self.assertTrue('user' in event)
            user_info = event['user']
            self.assertTrue('is_authenticated' in user_info)
            self.assertTrue(user_info['is_authenticated'])
            self.assertTrue('username' in user_info)
            self.assertEquals(user_info['username'], 'admin')
            self.assertFalse('email' in user_info)

    def test_user_info_with_non_django_auth(self):
        with self.settings(INSTALLED_APPS=[
            app for app in settings.INSTALLED_APPS
            if app != 'django.contrib.auth'
        ]):
            self.assertRaises(Exception,
                              self.client.get,
                              reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)
            self.assertFalse('user' in event)

    def test_request_middleware_exception(self):
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenRequestMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'request')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: request')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_request')

    def test_response_middlware_exception(self):
        if django.VERSION[:2] < (1, 3):
            return
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenResponseMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-no-error'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'response')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: response')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_response')

    def test_broken_500_handler_with_middleware(self):
        with self.settings(BREAK_THAT_500=True):
            client = TestClient(REMOTE_ADDR='127.0.0.1')
            client.handler = MockOpbeatMiddleware(MockClientHandler())

            self.assertRaises(Exception, client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 2)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'Exception')
            self.assertEquals(exc['value'], 'view exception')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'Exception: view exception')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')

            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ValueError')
            self.assertEquals(exc['value'], 'handler500')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ValueError: handler500')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.urls.handler500')

    def test_view_middleware_exception(self):
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.testapp.middleware.BrokenViewMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'view')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: view')
            self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.middleware.process_view')

    def test_exclude_modules_view(self):
        exclude_paths = self.opbeat.exclude_paths
        self.opbeat.exclude_paths = ['tests.views.decorated_raise_exc']
        self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc-decor'))

        self.assertEquals(len(self.opbeat.events), 1, self.opbeat.events)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'tests.contrib.django.testapp.views.raise_exc')
        self.opbeat.exclude_paths = exclude_paths

    def test_include_modules(self):
        include_paths = self.opbeat.include_paths
        self.opbeat.include_paths = ['django.shortcuts.get_object_or_404']

        self.assertRaises(Exception, self.client.get, reverse('opbeat-django-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'django.shortcuts.get_object_or_404')
        self.opbeat.include_paths = include_paths

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
                self.client.get, reverse('opbeat-template-exc')
            )

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

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
        handler = OpbeatHandler()
        handler.emit(record)

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['param_message'], {'message': 'test','params':()})

    def test_404_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.Opbeat404CatchMiddleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertEquals(event['level'], 'info')
            self.assertEquals(event['logger'], 'http404')

            self.assertTrue('http' in event)
            http = event['http']
            self.assertEquals(http['url'], u'http://testserver/non-existant-page')
            self.assertEquals(http['method'], 'GET')
            self.assertEquals(http['query_string'], '')
            self.assertEquals(http['data'], None)

    def test_404_middleware_with_debug(self):
        with self.settings(
                MIDDLEWARE_CLASSES=[
                    'opbeat.contrib.django.middleware.Opbeat404CatchMiddleware'
                ],
                DEBUG=True,
        ):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            self.assertEquals(len(self.opbeat.events), 0)

    def test_response_error_id_middleware(self):
        with self.settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.OpbeatResponseErrorIdMiddleware', 'opbeat.contrib.django.middleware.Opbeat404CatchMiddleware']):
            resp = self.client.get('/non-existant-page')
            self.assertEquals(resp.status_code, 404)
            headers = dict(resp.items())
            self.assertTrue('X-Opbeat-ID' in headers)
            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)
            self.assertEquals('$'.join(event['client_supplied_id']), headers['X-Opbeat-ID'])

    def test_get_client(self):
        self.assertEquals(get_client(), get_client())
        self.assertEquals(get_client('opbeat.base.Client').__class__, Client)
        self.assertEquals(get_client(), self.opbeat)

        self.assertEquals(get_client('%s.%s' % (self.opbeat.__class__.__module__, self.opbeat.__class__.__name__)), self.opbeat)
        self.assertEquals(get_client(), self.opbeat)

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
            'CONTENT_TYPE': 'application/octet-stream',
            'CONTENT_LENGTH': len(v),
            'ACCEPT': 'application/json',
        })
        request.read(1)

        self.opbeat.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['method'], 'POST')
        self.assertEquals(http['data'], '<unavailable>')

    def test_post_data(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/octet-stream',
            'ACCEPT': 'application/json',
        })
        request.POST = QueryDict("x=1&y=2")
        self.opbeat.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['method'], 'POST')
        self.assertEquals(http['data'], {'x': '1', 'y': '2'})

    def test_post_raw_data(self):
        request = WSGIRequest(environ={
            'wsgi.input': six.BytesIO(six.b('foobar')),
            'REQUEST_METHOD': 'POST',
            'SERVER_NAME': 'testserver',
            'SERVER_PORT': '80',
            'CONTENT_TYPE': 'application/octet-stream',
            'ACCEPT': 'application/json',
            'CONTENT_LENGTH': '6',
        })
        self.opbeat.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['method'], 'POST')
        self.assertEquals(http['data'], six.b('foobar'))

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

        self.opbeat.capture('Message', message='foo', request=request)

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['method'], 'POST')
        self.assertEquals(http['data'], '<unavailable>')
        self.assertTrue('headers' in http)
        headers = http['headers']
        self.assertTrue('Content-Type' in headers, headers.keys())
        self.assertEquals(headers['Content-Type'], 'text/html')
        env = http['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'testserver')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_transaction_metrics(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store
        with self.settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            self.assertEqual(len(self.opbeat.instrumentation_store), 0)
            self.client.get(reverse('opbeat-no-error'))
            self.assertEqual(len(self.opbeat.instrumentation_store), 1)

            transactions, traces = self.opbeat.instrumentation_store.get_all()

            self.assertEqual(len(transactions), 1)
            timing = transactions[0]
            self.assertTrue('durations' in timing)
            self.assertEqual(len(timing['durations']), 1)
            self.assertEqual(timing['transaction'],
                             'GET tests.contrib.django.testapp.views.no_error')
            self.assertEqual(timing['result'],
                             200)

    def test_request_metrics_301_append_slash(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            APPEND_SLASH=True,
        ):
            self.client.get(reverse('opbeat-no-error-slash')[:-1])
        timed_requests, _traces = self.opbeat.instrumentation_store.get_all()
        timing = timed_requests[0]
        self.assertIn(
            timing['transaction'], (
                # django <= 1.8
                'GET django.middleware.common.CommonMiddleware.process_request',
                # django 1.9+
                'GET django.middleware.common.CommonMiddleware.process_response',
            )
        )

    def test_request_metrics_301_prepend_www(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware',
                'django.middleware.common.CommonMiddleware',
            ],
            PREPEND_WWW=True,
        ):
            self.client.get(reverse('opbeat-no-error'))
        timed_requests, _traces = self.opbeat.instrumentation_store.get_all()
        timing = timed_requests[0]
        self.assertEqual(
            timing['transaction'],
            'GET django.middleware.common.CommonMiddleware.process_request'
        )

    def test_request_metrics_contrib_redirect(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store

        # enable middleware wrapping
        client = get_client()
        client.instrument_django_middleware = True
        from opbeat.contrib.django.middleware import OpbeatAPMMiddleware
        OpbeatAPMMiddleware._opbeat_instrumented = False

        s = Site.objects.get(pk=1)
        Redirect.objects.create(site=s, old_path='/redirect/me/', new_path='/here/')

        with self.settings(
            MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware',
                'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
            ],
        ):
            response = self.client.get('/redirect/me/')

        timed_requests, _traces = self.opbeat.instrumentation_store.get_all()
        timing = timed_requests[0]
        self.assertEqual(
            timing['transaction'],
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
        with self.settings(OPBEAT=config):
            pytest.deprecated_call(get_client_config)

    def test_request_metrics_name_override(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store
        with self.settings(
            MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware',
                'tests.contrib.django.testapp.middleware.MetricsNameOverrideMiddleware',
            ]
        ):
            self.client.get(reverse('opbeat-no-error'))
        timed_requests, _traces = self.opbeat.instrumentation_store.get_all()
        timing = timed_requests[0]
        self.assertEqual(
            timing['transaction'],
            'GET foobar'
        )

    def test_request_metrics_404_resolve_error(self):
        self.opbeat.instrumentation_store.get_all()  # clear the store
        with self.settings(
                MIDDLEWARE_CLASSES=[
                    'opbeat.contrib.django.middleware.OpbeatAPMMiddleware',
                ]
        ):
            self.client.get('/i-dont-exist/')
        timed_requests, _traces = self.opbeat.instrumentation_store.get_all()
        timing = timed_requests[0]
        self.assertEqual(
            timing['transaction'],
            ''
        )


class DjangoClientNoTempTest(TestCase):
    def setUp(self):
        self.client = DjangoClient(
            servers=['http://example.com'],
            organization_id='org',
            app_id='app',
            secret_token='secret',
            filter_exception_types=['KeyError', 'tests.contrib.django.fake1.FakeException']
        )

    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_filter_no_match(self, send_encoded):
        try:
            raise ValueError('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 1)

    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type(self, send_encoded):
        try:
            raise KeyError('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 0)

    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type_but_not_module(self, send_encoded):
        try:
            from tests.contrib.django.fake2 import FakeException
            raise FakeException('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 1)

    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_filter_matches_type_and_module(self, send_encoded):
        try:
            from tests.contrib.django.fake1 import FakeException
            raise FakeException('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(send_encoded.call_count, 0)

    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
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
        self.opbeat = get_client()

    def test_request_kwarg(self):
        handler = OpbeatHandler()

        logger = self.logger
        logger.handlers = []
        logger.addHandler(handler)

        logger.error('This is a test error', extra={
            'request': WSGIRequest(environ={
                'wsgi.input': six.StringIO(),
                'REQUEST_METHOD': 'POST',
                'SERVER_NAME': 'testserver',
                'SERVER_PORT': '80',
                'CONTENT_TYPE': 'application/octet-stream',
                'ACCEPT': 'application/json',
            })
        })

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['method'], 'POST')


class CeleryIsolatedClientTest(TestCase):
    def setUp(self):
        self.client = CeleryClient(
            servers=['http://example.com'],
            organization_id='org',
            app_id='app',
            secret_token='secret',
        )

    @mock.patch('opbeat.contrib.django.celery.CeleryClient.send_raw')
    def test_send_encoded(self, send_raw):
        self.client.send_encoded('foo')

        send_raw.delay.assert_called_once_with('foo')

    @mock.patch('opbeat.contrib.django.celery.CeleryClient.send_raw')
    def test_without_eager(self, send_raw):
        """
        Integration test to ensure it propagates all the way down
        and calls delay on the task.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_raw.delay.call_count, 1)

    @pytest.mark.skipif(not has_with_eager_tasks,
                        reason='with_eager_tasks is not available')
    @with_eager_tasks
    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_with_eager(self, send_encoded):
        """
        Integration test to ensure it propagates all the way down
        and calls the parent client's send_encoded method.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_encoded.call_count, 1)


class CeleryIntegratedClientTest(TestCase):
    def setUp(self):
        self.client = CeleryClient(
            servers=['http://example.com'],
            organization_id='org',
            app_id='app',
            secret_token='secret',
        )

    @pytest.mark.skipif(not has_with_eager_tasks,
                        reason='with_eager_tasks is not available')
    @with_eager_tasks
    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_with_eager(self, send_encoded):
        """
        Integration test to ensure it propagates all the way down
        and calls the parent client's send_encoded method.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_encoded.call_count, 1)


def client_get(client, url):
    return client.get(url)


def test_stacktraces_have_templates():
    client = TestClient()
    opbeat = get_client()
    instrumentation.control.instrument()

    # Clear the LRU frame cache
    Transaction._lrucache = LRUCache(maxsize=5000)

    # only Django 1.9+ have the necessary information stored on Node/Template
    # instances when TEMPLATE_DEBUG = False

    TEMPLATE_DEBUG = django.VERSION < (1, 9)

    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        TEMPLATES_copy = deepcopy(settings.TEMPLATES)
        TEMPLATES_copy[0]['OPTIONS']['debug'] = TEMPLATE_DEBUG
        with override_settings(
            MIDDLEWARE_CLASSES=[
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'
            ],
            TEMPLATE_DEBUG=TEMPLATE_DEBUG,
            TEMPLATES=TEMPLATES_copy
        ):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions, traces = opbeat.instrumentation_store.get_all()
    assert len(transactions) == 1
    assert len(traces) == 3, [t["signature"] for t in traces]

    expected_signatures = ['transaction', 'list_users.html',
                           'something_expensive']

    assert set([t['signature'] for t in traces]) == set(expected_signatures)

    # Reorder according to the kinds list so we can just test them
    sig_dict = dict([(t['signature'], t) for t in traces])
    traces = [sig_dict[k] for k in expected_signatures]

    assert traces[2]['signature'] == 'something_expensive'

    # Find the template
    for frame in traces[2]['extra']['_frames']:
        if frame['lineno'] == 4 and frame['filename'].endswith('django/testapp/templates/list_users.html'):
            break
    else:
        assert False is True, "Template was not found"


def test_stacktrace_filtered_for_opbeat():
    client = TestClient()
    opbeat = get_client()
    instrumentation.control.instrument()

    # Clear the LRU frame cache
    Transaction._lrucache = LRUCache(maxsize=5000)

    with mock.patch(
            "opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(MIDDLEWARE_CLASSES=[
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions, traces = opbeat.instrumentation_store.get_all()

    expected_signatures = ['transaction', 'list_users.html',
                           'something_expensive']

    # Reorder according to the kinds list so we can just test them
    sig_dict = dict([(t['signature'], t) for t in traces])
    traces = [sig_dict[k] for k in expected_signatures]

    assert traces[1]['signature'] == 'list_users.html'
    frames = traces[1]['extra']['_frames']

    # Top frame should be inside django rendering
    assert frames[0]['module'].startswith('django.template')


def test_perf_template_render(benchmark):
    client = TestClient()
    opbeat = get_client()
    instrumentation.control.instrument()
    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        with override_settings(MIDDLEWARE_CLASSES=[
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            resp = benchmark(client_get, client, reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions, traces = opbeat.instrumentation_store.get_all()

    # If the test falls right at the change from one minute to another
    # this will have two items.
    assert 0 < len(transactions) < 3, [t["transaction"] for t in transactions]
    assert len(traces) == 3, [t["signature"] for t in traces]


def test_perf_template_render_no_middleware(benchmark):
    client = TestClient()
    opbeat = get_client()
    instrumentation.control.instrument()
    with mock.patch(
            "opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = benchmark(client_get, client,
                         reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions, traces = opbeat.instrumentation_store.get_all()
    assert len(transactions) == 0
    assert len(traces) == 0


@pytest.mark.django_db(transaction=True)
def test_perf_database_render(benchmark):
    client = TestClient()

    opbeat = get_client()
    instrumentation.control.instrument()
    opbeat.instrumentation_store.get_all()

    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False

        with override_settings(MIDDLEWARE_CLASSES=[
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            resp = benchmark(client_get, client, reverse("render-user-template"))
        assert resp.status_code == 200

        transactions, traces = opbeat.instrumentation_store.get_all()

        # If the test falls right at the change from one minute to another
        # this will have two items.
        assert 0 < len(transactions) < 3, [t["transaction"] for t in transactions]
        assert len(traces) == 5, [t["signature"] for t in traces]


@pytest.mark.django_db
def test_perf_database_render_no_instrumentation(benchmark):
    opbeat = get_client()
    opbeat.instrumentation_store.get_all()
    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False

        client = TestClient()
        resp = benchmark(client_get, client, reverse("render-user-template"))

        assert resp.status_code == 200

        transactions, traces = opbeat.instrumentation_store.get_all()
        assert len(transactions) == 0
        assert len(traces) == 0


@pytest.mark.django_db
def test_perf_transaction_with_collection(benchmark):
    opbeat = get_client()
    opbeat.instrumentation_store.get_all()
    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        opbeat.events = []

        client = TestClient()

        with override_settings(MIDDLEWARE_CLASSES=[
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):

            for i in range(10):
                resp = client_get(client, reverse("render-user-template"))
                assert resp.status_code == 200

        assert len(opbeat.events) == 0

        # Force collection on next request
        should_collect.return_value = True

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert result.status_code is 200
        assert len(opbeat.events) > 0


@pytest.mark.django_db
def test_perf_transaction_without_middleware(benchmark):
    opbeat = get_client()
    opbeat.instrumentation_store.get_all()
    with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
        should_collect.return_value = False
        client = TestClient()
        opbeat.events = []
        for i in range(10):
            resp = client_get(client, reverse("render-user-template"))
            assert resp.status_code == 200

        assert len(opbeat.events) == 0

        @benchmark
        def result():
            # Code to be measured
            return client_get(client, reverse("render-user-template"))

        assert len(opbeat.events) == 0


class DjangoManagementCommandTest(TestCase):
    @mock.patch('opbeat.contrib.django.management.commands.opbeat.Command._get_argv')
    def test_subcommand_not_set(self, argv_mock):
        stdout = six.StringIO()
        command = DjangoCommand()
        argv_mock.return_value = ['manage.py', 'opbeat']
        command.execute(stdout=stdout)
        output = stdout.getvalue()
        assert 'No command specified' in output

    @mock.patch('opbeat.contrib.django.management.commands.opbeat.Command._get_argv')
    def test_subcommand_not_known(self, argv_mock):
        stdout = six.StringIO()
        command = DjangoCommand()
        argv_mock.return_value = ['manage.py', 'opbeat']
        command.execute('foo', stdout=stdout)
        output = stdout.getvalue()
        assert 'No such command "foo"' in output

    def test_settings_missing(self):
        stdout = six.StringIO()
        command = DjangoCommand()
        with self.settings(OPBEAT={}):
            command.execute('check', stdout=stdout)
        output = stdout.getvalue()
        assert 'Configuration errors detected' in output
        assert 'ORGANIZATION_ID not set' in output
        assert 'APP_ID not set' in output
        assert 'SECRET_TOKEN not set' in output

    def test_middleware_not_set(self):
        stdout = six.StringIO()
        command = DjangoCommand()
        with self.settings(MIDDLEWARE_CLASSES=()):
            command.execute('check', stdout=stdout)
        output = stdout.getvalue()
        assert 'Opbeat APM middleware not set!' in output

    def test_middleware_not_first(self):
        stdout = six.StringIO()
        command = DjangoCommand()
        with self.settings(MIDDLEWARE_CLASSES=(
            'foo',
            'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'
        )):
            command.execute('check', stdout=stdout)
        output = stdout.getvalue()
        assert 'not at the first position' in output

    @mock.patch('opbeat.transport.http.urlopen')
    def test_test_exception(self, urlopen_mock):
        stdout = six.StringIO()
        command = DjangoCommand()
        resp = six.moves.urllib.response.addinfo(
            mock.Mock(),
            headers={'Location': 'http://example.com'}
        )
        urlopen_mock.return_value = resp
        with self.settings(MIDDLEWARE_CLASSES=(
                'foo',
                'opbeat.contrib.django.middleware.OpbeatAPMMiddleware'
        )):
            command.execute('test', stdout=stdout, stderr=stdout)
        output = stdout.getvalue()
        assert 'http://example.com' in output
