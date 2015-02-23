# -*- coding: utf-8 -*-

from __future__ import absolute_import
from opbeat.utils import six
import datetime
import django
import logging
import mock
from opbeat.utils.six import StringIO, BytesIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.signals import got_request_exception
from django.core.handlers.wsgi import WSGIRequest
from django.template import TemplateSyntaxError
from django.test import TestCase
from django.test.utils import override_settings

from opbeat.base import Client
from opbeat.contrib.django import DjangoClient
from opbeat.contrib.django.celery import CeleryClient
from opbeat.contrib.django.handlers import OpbeatHandler
from opbeat.contrib.django.models import client, get_client as orig_get_client
from opbeat.contrib.django.middleware.wsgi import Opbeat
from opbeat.utils.compat import skipIf

try:
    from celery.tests.utils import with_eager_tasks
    has_with_eager_tasks = True
except ImportError:
    from opbeat.utils.compat import noop_decorator as with_eager_tasks
    has_with_eager_tasks = False

from django.test.client import Client as TestClient, ClientHandler as TestClientHandler

settings.OPBEAT = {'CLIENT': 'tests.contrib.django.django_tests.TempStoreClient'}


def get_client(*args, **kwargs):
    config = {
        'APP_ID': 'key',
        'ORGANIZATION_ID': 'org',
        'SECRET_TOKEN': '99'
    }
    config.update(settings.OPBEAT)

    with override_settings(OPBEAT=config):
        cli = orig_get_client(*args, **kwargs)
        return cli


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
    ## Fixture setup/teardown
    urls = 'tests.contrib.django.urls'

    def setUp(self):
        self.opbeat = get_client()
        self.opbeat.events = []

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
        self.assertEquals(event['culprit'], 'tests.contrib.django.views.raise_exc')

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

    @skipIf(django.VERSION < (1, 5), 'Custom user model was introduced with Django 1.5')
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
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenRequestMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'request')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: request')
            self.assertEquals(event['culprit'], 'tests.contrib.django.middleware.process_request')

    def test_response_middlware_exception(self):
        if django.VERSION[:2] < (1, 3):
            return
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenResponseMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-no-error'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'response')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: response')
            self.assertEquals(event['culprit'], 'tests.contrib.django.middleware.process_response')

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
            self.assertEquals(event['culprit'], 'tests.contrib.django.views.raise_exc')

            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ValueError')
            self.assertEquals(exc['value'], 'handler500')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ValueError: handler500')
            self.assertEquals(event['culprit'], 'tests.contrib.django.urls.handler500')

    def test_view_middleware_exception(self):
        with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenViewMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('opbeat-raise-exc'))

            self.assertEquals(len(self.opbeat.events), 1)
            event = self.opbeat.events.pop(0)

            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ImportError')
            self.assertEquals(exc['value'], 'view')
            self.assertEquals(event['level'], 'error')
            self.assertEquals(event['message'], 'ImportError: view')
            self.assertEquals(event['culprit'], 'tests.contrib.django.middleware.process_view')

    def test_exclude_modules_view(self):
        exclude_paths = self.opbeat.exclude_paths
        self.opbeat.exclude_paths = ['tests.views.decorated_raise_exc']
        self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc-decor'))

        self.assertEquals(len(self.opbeat.events), 1, self.opbeat.events)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'tests.contrib.django.views.raise_exc')
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
        self.assertRaises(TemplateSyntaxError, self.client.get, reverse('opbeat-template-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'error.html')

    # def test_request_in_logging(self):
    #     resp = self.client.get(reverse('opbeat-log-request-exc'))
    #     self.assertEquals(resp.status_code, 200)

    #     self.assertEquals(len(self.opbeat.events), 1)
    #     event = self.opbeat.events.pop(0)

    #     self.assertEquals(event['culprit'], 'tests.contrib.django.views.logging_request_exc')
    #     self.assertEquals(event['data']['META']['REMOTE_ADDR'], '127.0.0.1')

    @skipIf(six.PY3, 'see Python bug #10805')
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

    # def test_response_error_id_middleware(self):
    #     # TODO: test with 500s
    #     with self.settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.OpbeatResponseErrorIdMiddleware', 'opbeat.contrib.django.middleware.Opbeat404CatchMiddleware']):
    #         resp = self.client.get('/non-existant-page')
    #         self.assertEquals(resp.status_code, 404)
    #         headers = dict(resp.items())
    #         self.assertTrue('X-Opbeat-ID' in headers)
    #         self.assertEquals(len(self.opbeat.events), 1)
    #         event = self.opbeat.events.pop(0)
    #         self.assertEquals('$'.join([event['client_supplied_id'], event['checksum']]), headers['X-Opbeat-ID'])

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
            'wsgi.input': BytesIO(v + six.b('\r\n\r\n')),
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

    # This test only applies to Django 1.3+
    def test_request_capture(self):
        if django.VERSION[:2] < (1, 3):
            return
        request = WSGIRequest(environ={
            'wsgi.input': StringIO(),
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

    ## TODO: Find out why this is broken
    # def test_filtering_middleware(self):
    #     with self.settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.FilteringMiddleware']):
    #         self.assertRaises(IOError, self.client.get, reverse('opbeat-raise-ioerror'))
    #         self.assertEquals(len(self.opbeat.events), 0)
    #         self.assertRaises(Exception, self.client.get, reverse('opbeat-raise-exc'))
    #         self.assertEquals(len(self.opbeat.events), 1)
    #         self.opbeat.events.pop(0)

    def test_request_metrics(self):
        self.opbeat._requests_store.get_all()  # clear the store
        with self.settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.OpbeatAPMMiddleware']):
            self.assertEqual(len(self.opbeat._requests_store), 0)
            self.client.get(reverse('opbeat-no-error'))
            self.assertEqual(len(self.opbeat._requests_store), 1)
            timed_requests = self.opbeat._requests_store.get_all()

            self.assertEqual(len(timed_requests), 1)
            timing = timed_requests[0]
            self.assertTrue('durations' in timing)
            self.assertEqual(len(timing['durations']), 1)
            self.assertEqual(timing['transaction'],
                             'tests.contrib.django.views.no_error')
            self.assertEqual(timing['result'],
                             200)


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
                'wsgi.input': StringIO(),
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

    @skipIf(not has_with_eager_tasks, 'with_eager_tasks is not available')
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

    @skipIf(not has_with_eager_tasks, 'with_eager_tasks is not available')
    @with_eager_tasks
    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_with_eager(self, send_encoded):
        """
        Integration test to ensure it propagates all the way down
        and calls the parent client's send_encoded method.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_encoded.call_count, 1)
