# -*- coding: utf-8 -*-

from __future__ import absolute_import

import datetime
import django
import logging
import mock
import re
from celery.tests.utils import with_eager_tasks
from StringIO import StringIO

from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.signals import got_request_exception
from django.core.handlers.wsgi import WSGIRequest
from django.template import TemplateSyntaxError
from django.test import TestCase

from opbeat.base import Client
from opbeat.contrib.django import DjangoClient
from opbeat.contrib.django.celery import CeleryClient
from opbeat.contrib.django.handlers import OpbeatHandler
from opbeat.contrib.django.models import client, get_client as orig_get_client
from opbeat.contrib.django.middleware.wsgi import Opbeat
from opbeat.contrib.django.views import is_valid_origin

from django.test.client import Client as TestClient, ClientHandler as TestClientHandler

settings.OPBEAT_CLIENT = 'tests.contrib.django.django_tests.TempStoreClient'

def get_client(*args,**kwargs):
    with Settings(OPBEAT_ACCESS_TOKEN='key',OPBEAT_PROJECT_ID='99'):
        cli = orig_get_client(*args,**kwargs)
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


class Settings(object):
    """
    Allows you to define settings that are required for this function to work.

    >>> with Settings(SENTRY_LOGIN_URL='foo'): #doctest: +SKIP
    >>>     print settings.SENTRY_LOGIN_URL #doctest: +SKIP
    """

    NotDefined = object()

    def __init__(self, **overrides):
        self.overrides = overrides
        self._orig = {}

    def __enter__(self):
        for k, v in self.overrides.iteritems():
            self._orig[k] = getattr(settings, k, self.NotDefined)
            setattr(settings, k, v)

    def __exit__(self, exc_type, exc_value, traceback):
        for k, v in self._orig.iteritems():
            if v is self.NotDefined:
                delattr(settings, k)
            else:
                setattr(settings, k, v)


class ClientProxyTest(TestCase):
    def test_proxy_responds_as_client(self):
        self.assertEquals(get_client(), client)

    def test_basic(self):
        with Settings(OPBEAT_ACCESS_TOKEN='key',OPBEAT_PROJECT_ID='99'):
            client.capture('Message', message='foo')
            self.assertEquals(len(client.events), 1)
            client.events.pop(0)


class DjangoClientTest(TestCase):
    ## Fixture setup/teardown
    urls = 'tests.contrib.django.urls'

    def setUp(self):
        self.opbeat = get_client()

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
        self.assertRaises(Exception, self.client.get, reverse('sentry-raise-exc'))

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

        self.assertRaises(Exception, self.client.get, reverse('sentry-raise-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)
        self.assertTrue('user' in event)
        user_info = event['user']
        self.assertTrue('is_authenticated' in user_info)
        self.assertFalse(user_info['is_authenticated'])
        self.assertFalse('username' in user_info)
        self.assertFalse('email' in user_info)

        self.assertTrue(self.client.login(username='admin', password='admin'))

        self.assertRaises(Exception, self.client.get, reverse('sentry-raise-exc'))

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

    def test_request_middleware_exception(self):
        with Settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenRequestMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('sentry-raise-exc'))

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
        with Settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenResponseMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('sentry-no-error'))

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
        with Settings(BREAK_THAT_500=True):
            client = TestClient(REMOTE_ADDR='127.0.0.1')
            client.handler = MockOpbeatMiddleware(MockClientHandler())

            self.assertRaises(Exception, client.get, reverse('sentry-raise-exc'))

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
        with Settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.BrokenViewMiddleware']):
            self.assertRaises(ImportError, self.client.get, reverse('sentry-raise-exc'))

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
        self.assertRaises(Exception, self.client.get, reverse('sentry-raise-exc-decor'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'tests.contrib.django.views.raise_exc')
        self.opbeat.exclude_paths = exclude_paths

    def test_include_modules(self):
        include_paths = self.opbeat.include_paths
        self.opbeat.include_paths = ['django.shortcuts.get_object_or_404']

        self.assertRaises(Exception, self.client.get, reverse('sentry-django-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'django.shortcuts.get_object_or_404')
        self.opbeat.include_paths = include_paths

    def test_template_name_as_view(self):
        self.assertRaises(TemplateSyntaxError, self.client.get, reverse('sentry-template-exc'))

        self.assertEquals(len(self.opbeat.events), 1)
        event = self.opbeat.events.pop(0)

        self.assertEquals(event['culprit'], 'error.html')

    # def test_request_in_logging(self):
    #     resp = self.client.get(reverse('sentry-log-request-exc'))
    #     self.assertEquals(resp.status_code, 200)

    #     self.assertEquals(len(self.opbeat.events), 1)
    #     event = self.opbeat.events.pop(0)

    #     self.assertEquals(event['culprit'], 'tests.contrib.django.views.logging_request_exc')
    #     self.assertEquals(event['data']['META']['REMOTE_ADDR'], '127.0.0.1')

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

        self.assertEquals(event['param_message'], {'message':'test','params':()})

    def test_404_middleware(self):
        with Settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.Opbeat404CatchMiddleware']):
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
    #     with Settings(MIDDLEWARE_CLASSES=['opbeat.contrib.django.middleware.OpbeatResponseErrorIdMiddleware', 'opbeat.contrib.django.middleware.Opbeat404CatchMiddleware']):
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
        v = '{"foo": "bar"}'
        request = WSGIRequest(environ={
            'wsgi.input': StringIO(v + '\r\n\r\n'),
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
    #     with Settings(MIDDLEWARE_CLASSES=['tests.contrib.django.middleware.FilteringMiddleware']):
    #         self.assertRaises(IOError, self.client.get, reverse('sentry-raise-ioerror'))
    #         self.assertEquals(len(self.opbeat.events), 0)
    #         self.assertRaises(Exception, self.client.get, reverse('sentry-raise-exc'))
    #         self.assertEquals(len(self.opbeat.events), 1)
    #         self.opbeat.events.pop(0)


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
            project_id='public',
            access_token='secret',
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
            project_id='public',
            access_token='secret',
        )

    @mock.patch('opbeat.contrib.django.celery.CeleryClient.send_raw_integrated')
    def test_send_encoded(self, send_raw):
        self.client.send_integrated('foo')

        send_raw.delay.assert_called_once_with('foo')

    ## NO direct sending
    # @mock.patch('opbeat.contrib.django.celery.CeleryClient.send_raw_integrated')
    # def test_without_eager(self, send_raw):
    #     """
    #     Integration test to ensure it propagates all the way down
    #     and calls delay on the task.
    #     """
    #     self.client.capture('Message', message='test')

    #     self.assertEquals(send_raw.delay.call_count, 1)

    @with_eager_tasks
    @mock.patch('opbeat.contrib.django.DjangoClient.send_encoded')
    def test_with_eager(self, send_encoded):
        """
        Integration test to ensure it propagates all the way down
        and calls the parent client's send_encoded method.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_encoded.call_count, 1)


class IsValidOriginTestCase(TestCase):
    def test_setting_empty(self):
        with Settings(SENTRY_ALLOW_ORIGIN=None):
            self.assertFalse(is_valid_origin('http://example.com'))

    def test_setting_all(self):
        with Settings(SENTRY_ALLOW_ORIGIN='*'):
            self.assertTrue(is_valid_origin('http://example.com'))

    def test_setting_uri(self):
        with Settings(SENTRY_ALLOW_ORIGIN=['http://example.com']):
            self.assertTrue(is_valid_origin('http://example.com'))

    def test_setting_regexp(self):
        with Settings(SENTRY_ALLOW_ORIGIN=[re.compile('https?\://(.*\.)?example\.com')]):
            self.assertTrue(is_valid_origin('http://example.com'))


# class ReportViewTest(TestCase):
#     urls = 'opbeat.contrib.django.urls'

#     def setUp(self):
#         self.path = reverse('opbeat-report')

#     def test_does_not_allow_get(self):
#         resp = self.client.get(self.path)
#         self.assertEquals(resp.status_code, 405)

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin')
#     def test_calls_is_valid_origin_with_header(self, is_valid_origin):
#         self.client.post(self.path, HTTP_ORIGIN='http://example.com')
#         is_valid_origin.assert_called_once_with('http://example.com')

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=False))
#     def test_fails_on_invalid_origin(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com')
#         self.assertEquals(resp.status_code, 403)

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_options_call_sends_headers(self):
#         resp = self.client.options(self.path, HTTP_ORIGIN='http://example.com')
#         self.assertEquals(resp.status_code, 200)
#         self.assertEquals(resp['Access-Control-Allow-Origin'], 'http://example.com')
#         self.assertEquals(resp['Access-Control-Allow-Methods'], 'POST, OPTIONS')

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_missing_data(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com')
#         self.assertEquals(resp.status_code, 400)

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_invalid_data(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com',
#             data='[1', content_type='application/octet-stream')
#         self.assertEquals(resp.status_code, 400)

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_sends_data(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com',
#             data='{}', content_type='application/octet-stream')
#         self.assertEquals(resp.status_code, 200)
#         event = client.events.pop(0)
#         self.assertEquals(event, {'auth_header': None})

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_sends_authorization_header(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com',
#             HTTP_AUTHORIZATION='Opbeat foo/bar', data='{}', content_type='application/octet-stream')
#         self.assertEquals(resp.status_code, 200)
#         event = client.events.pop(0)
#         self.assertEquals(event, {'auth_header': 'Opbeat foo/bar'})

#     @mock.patch('opbeat.contrib.django.views.is_valid_origin', mock.Mock(return_value=True))
#     def test_sends_x_sentry_auth_header(self):
#         resp = self.client.post(self.path, HTTP_ORIGIN='http://example.com',
#             HTTP_X_SENTRY_AUTH='Opbeat foo/bar', data='{}', content_type='application/octet-stream')
#         self.assertEquals(resp.status_code, 200)
#         event = client.events.pop(0)
#         self.assertEquals(event, {'auth_header': 'Opbeat foo/bar'})
