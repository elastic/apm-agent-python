# -*- coding: utf-8 -*-
import platform
import time

import mock
import pytest

import opbeat
from opbeat.base import Client, ClientState
from opbeat.conf import defaults
from opbeat.transport.base import Transport, TransportException
from opbeat.transport.http import HTTPTransport
from opbeat.utils import six
from opbeat.utils.compat import urlparse
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class ClientStateTest(TestCase):
    def test_should_try_online(self):
        state = ClientState()
        self.assertEquals(state.should_try(), True)

    def test_should_try_new_error(self):
        state = ClientState()
        state.status = state.ERROR
        state.last_check = time.time()
        state.retry_number = 1
        self.assertEquals(state.should_try(), False)

    def test_should_try_time_passed_error(self):
        state = ClientState()
        state.status = state.ERROR
        state.last_check = time.time() - 10
        state.retry_number = 1
        self.assertEquals(state.should_try(), True)

    def test_set_fail(self):
        state = ClientState()
        state.set_fail()
        self.assertEquals(state.status, state.ERROR)
        self.assertNotEquals(state.last_check, None)
        self.assertEquals(state.retry_number, 1)

    def test_set_success(self):
        state = ClientState()
        state.status = state.ERROR
        state.last_check = 'foo'
        state.retry_number = 0
        state.set_success()
        self.assertEquals(state.status, state.ONLINE)
        self.assertEquals(state.last_check, None)
        self.assertEquals(state.retry_number, 0)


class DummyTransport(Transport):
    def send(self, data, headers):
        pass


class ClientTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()

    def test_platform_info(self):
        platform_info = self.client.get_platform_info()
        self.assertIn(
            'lang=python/' + platform.python_version(),
            platform_info,
        )
        self.assertIn(
            'platform=' + platform.python_implementation(),
            platform_info,
        )

    def test_config_by_environment(self):
        with mock.patch.dict('os.environ', {
            'OPBEAT_ORGANIZATION_ID': 'org',
            'OPBEAT_APP_ID': 'app',
            'OPBEAT_SECRET_TOKEN': 'token',
        }):
            client = Client()
            self.assertEqual(client.organization_id, 'org')
            self.assertEqual(client.app_id, 'app')
            self.assertEqual(client.secret_token, 'token')
            self.assertEqual(client.is_send_disabled, False)
        with mock.patch.dict('os.environ', {
            'OPBEAT_DISABLE_SEND': 'true',
        }):
            client = Client()
            self.assertEqual(client.is_send_disabled, True)

    @mock.patch('opbeat.base.Client.send')
    def test_config_non_string_types(self, mock_send):
        """
        tests if we can handle non string types as configuration, e.g.
        Value types from django-configuration
        """
        class MyValue(object):
            def __init__(self, content):
                self.content = content

            def __str__(self):
                return str(self.content)

            def __repr__(self):
                return repr(self.content)

        client = Client(
            servers=['localhost'],
            organization_id=MyValue('foo'),
            app_id=MyValue('bar'),
            secret_token=MyValue('bay')
        )
        client.capture('Message', message='foo')
        args, kwargs = mock_send.call_args
        self.assertEqual(
            'localhost' + defaults.ERROR_API_PATH.format('foo', 'bar'),
            kwargs['servers'][0]
        )

    def test_custom_transport(self):
        client = Client(
            servers=['localhost'],
            organization_id='foo',
            app_id='bar',
            secret_token='baz',
            transport_class='tests.client.client_tests.DummyTransport',
        )
        self.assertEqual(client._transport_class, DummyTransport)

    def test_empty_processor_list(self):
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            processors=[],
        )

        self.assertEqual(client.processors, [])

    @mock.patch('opbeat.transport.http_urllib3.Urllib3Transport.send')
    @mock.patch('opbeat.base.ClientState.should_try')
    def test_send_remote_failover_sync(self, should_try, http_send):
        should_try.return_value = True

        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=False,
        )
        logger = mock.Mock()
        client.error_logger.error = logger

        # test error
        encoded_data = client.encode({'message': 'oh no'})
        http_send.side_effect = TransportException('oopsie', encoded_data)
        client.send_remote('http://example.com/api/store', data=encoded_data)
        assert client.state.status == client.state.ERROR
        assert len(logger.call_args_list) == 2
        assert 'oopsie' in logger.call_args_list[0][0][0]
        assert 'oh no' in logger.call_args_list[1][0][1]

        # test recovery
        http_send.side_effect = None
        client.send_remote('http://example.com/api/store', 'foo')
        assert client.state.status == client.state.ONLINE

    @mock.patch('opbeat.transport.http_urllib3.Urllib3Transport.send')
    @mock.patch('opbeat.base.ClientState.should_try')
    def test_send_remote_failover_async(self, should_try, http_send):
        should_try.return_value = True

        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=True,
        )
        logger = mock.Mock()
        client.error_logger.error = logger

        # test error
        encoded_data = client.encode({'message': 'oh no'})
        http_send.side_effect = TransportException('oopsie', encoded_data)
        client.send_remote('http://example.com/api/store', data=encoded_data)
        client.close()
        assert client.state.status == client.state.ERROR
        assert len(logger.call_args_list) == 2
        assert 'oopsie' in logger.call_args_list[0][0][0]
        assert 'oh no' in logger.call_args_list[1][0][1]

        # test recovery
        http_send.side_effect = None
        client.send_remote('http://example.com/api/store', 'foo')
        client.close()
        assert client.state.status == client.state.ONLINE

    @mock.patch('opbeat.base.Client.send_remote')
    @mock.patch('opbeat.base.time.time')
    def test_send(self, time, send_remote):
        time.return_value = 1328055286.51
        public = "public"
        access_token = "secret"
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
        )
        client.send(**{
            'foo': 'bar',
        })
        send_remote.assert_called_once_with(
            url='http://example.com',
            data=six.b('x\x9c\xabVJ\xcb\xcfW\xb2RPJJ,R\xaa\x05\x00 \x98\x04T'),
            headers={
                'Content-Type': 'application/octet-stream',
                'Authorization': 'Bearer %s' % (access_token),
                'User-Agent': 'opbeat-python/%s' % opbeat.VERSION,
                'X-Opbeat-Platform': self.client.get_platform_info(),
            },
        )

    @mock.patch('opbeat.base.Client.send_remote')
    @mock.patch('opbeat.base.time.time')
    def test_send_not_enabled(self, time, send_remote):
        time.return_value = 1328055286.51
        with mock.patch.dict('os.environ', {'OPBEAT_DISABLE_SEND': 'true'}):
            client = Client(
                servers=['http://example.com'],
                organization_id='organization_id',
                app_id='app_id',
                secret_token='secret',
            )
        client.send(**{
            'foo': 'bar',
        })

        assert not send_remote.called

    @mock.patch('opbeat.base.Client.send_remote')
    @mock.patch('opbeat.base.time.time')
    def test_send_with_auth_header(self, time, send_remote):
        time.return_value = 1328055286.51
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
        )
        client.send(auth_header='foo', **{
            'foo': 'bar',
        })
        send_remote.assert_called_once_with(
            url='http://example.com',
            data=six.b('x\x9c\xabVJ\xcb\xcfW\xb2RPJJ,R\xaa\x05\x00 \x98\x04T'),
            headers={
                'Content-Type': 'application/octet-stream',
                'Authorization': 'foo',
                'User-Agent': 'opbeat-python/%s' % opbeat.VERSION,
                'X-Opbeat-Platform': self.client.get_platform_info(),
            },
        )

    @mock.patch('opbeat.transport.http_urllib3.Urllib3Transport.send')
    @mock.patch('opbeat.transport.http_urllib3.Urllib3Transport.close')
    @mock.patch('opbeat.base.Client._traces_collect')
    def test_client_shutdown_sync(self, mock_traces_collect, mock_close,
                                  mock_send):
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=False,
        )
        client.send(auth_header='foo', **{
            'foo': 'bar',
        })
        client.close()
        self.assertEqual(mock_close.call_count, 1)
        self.assertEqual(mock_traces_collect.call_count, 1)

    @mock.patch('opbeat.transport.http_urllib3.Urllib3Transport.send')
    @mock.patch('opbeat.base.Client._traces_collect')
    def test_client_shutdown_async(self, mock_traces_collect, mock_send):
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=True,
        )
        client.send(auth_header='foo', **{
            'foo': 'bar',
        })
        client.close()
        self.assertEqual(mock_traces_collect.call_count, 1)
        self.assertEqual(mock_send.call_count, 1)

    def test_encode_decode(self):
        data = {'foo': 'bar'}
        encoded = self.client.encode(data)
        self.assertTrue(type(encoded), str)
        self.assertEquals(data, self.client.decode(encoded))

    def test_explicit_message_on_message_event(self):
        self.client.capture('Message', message='test', data={
            'message': 'foo'
        })

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['message'], 'foo')

    def test_explicit_message_on_exception_event(self):
        try:
            raise ValueError('foo')
        except:
            self.client.capture('Exception', data={'message': 'foobar'})

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['message'], 'foobar')

    def test_exception_event(self):
        try:
            raise ValueError('foo')
        except:
            self.client.capture('Exception')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['message'], 'ValueError: foo')
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], 'foo')
        self.assertEquals(exc['module'], ValueError.__module__)  # this differs in some Python versions
        self.assertTrue('stacktrace' in event)
        frames = event['stacktrace']
        self.assertEquals(len(frames['frames']), 1)
        frame = frames['frames'][0]
        self.assertEquals(frame['abs_path'], __file__.replace('.pyc', '.py'))
        self.assertEquals(frame['filename'], 'tests/client/client_tests.py')
        self.assertEquals(frame['module'], __name__)
        self.assertEquals(frame['function'], 'test_exception_event')
        self.assertTrue('timestamp' in event)

    def test_message_event(self):
        self.client.capture('Message', message='test')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['message'], 'test')
        self.assertFalse('stacktrace' in event)
        self.assertTrue('timestamp' in event)

    # def test_stack_explicit_frames(self):
    #     def bar():
    #         return inspect.stack()

    #     frames = bar()

    #     self.client.capture('test', stack=iter_stack_frames(frames))

    #     self.assertEquals(len(self.client.events), 1)
    #     event = self.client.events.pop(0)
    #     self.assertEquals(event['message'], 'test')
    #     self.assertTrue('stacktrace' in event)
    #     self.assertEquals(len(frames), len(event['stacktrace']['frames']))
    #     for frame, frame_i in zip(frames, event['stacktrace']['frames']):
    #         self.assertEquals(frame[0].f_code.co_filename, frame_i['abs_path'])
    #         self.assertEquals(frame[0].f_code.co_name, frame_i['function'])

    # def test_stack_auto_frames(self):
    #     self.client.create_from_text('test', stack=True)

    #     self.assertEquals(len(self.client.events), 1)
    #     event = self.client.events.pop(0)
    #     self.assertEquals(event['message'], 'test')
    #     self.assertTrue('stacktrace' in event)
    #     self.assertTrue('timestamp' in event)

    # def test_site(self):
    #     self.client.capture('Message', message='test', data={'site': 'test'})

    #     self.assertEquals(len(self.client.events), 1)
    #     event = self.client.events.pop(0)
    #     self.assertEquals(event['site'], 'test')
    #     self.assertTrue('timestamp' in event)

    # def test_implicit_site(self):
    #     self.client = TempStoreClient(site='foo')
    #     self.client.capture('Message', message='test')

    #     self.assertEquals(len(self.client.events), 1)
    #     event = self.client.events.pop(0)
    #     self.assertEquals(event['site'], 'foo')

    def test_logger(self):
        self.client.capture('Message', message='test', data={'logger': 'test'})

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['logger'], 'test')
        self.assertTrue('timestamp' in event)

    def test_long_message(self):
        message = 'm' * 201

        self.client.capture('Message', message=message)

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertTrue(len(event['message']) < 201, len(event['message']))

    def test_long_culprit(self):
        culprit = 'c' * 101

        self.client.capture('Message', message='test', data={'culprit':culprit})

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertTrue(len(event['culprit']) < 101, len(event['culprit']))

    def test_long_logger(self):
        logger = 'c' * 61

        self.client.capture('Message', message='test', data={'logger':logger})

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertTrue(len(event['logger']) < 61, len(event['logger']))

    @mock.patch('opbeat.base.Client.send')
    @mock.patch('opbeat.base.RequestsStore.should_collect')
    def test_metrics_collection(self, should_collect, mock_send):
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
        )
        should_collect.return_value = False
        for i in range(7):
            client.begin_transaction("transaction.test")
            client.end_transaction('test-transaction', 200)

        self.assertEqual(len(client.instrumentation_store), 7)
        self.assertEqual(mock_send.call_count, 0)
        should_collect.return_value = True

        client.begin_transaction("transaction.test")
        client.end_transaction('my-other-transaction', 200)
        self.assertEqual(len(client.instrumentation_store), 0)
        self.assertEqual(mock_send.call_count, 1)

    @mock.patch('opbeat.base.Client.send')
    @mock.patch('opbeat.base.RequestsStore.should_collect')
    def test_call_end_twice(self, should_collect, mock_send):
        client = get_tempstoreclient()

        should_collect.return_value = False
        client.begin_transaction("celery")

        client.end_transaction('test-transaction', 200)
        client.end_transaction('test-transaction', 200)

    def test_async_arg_deprecation(self):
        pytest.deprecated_call(
            Client,
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async=True,
        )

    @mock.patch('opbeat.utils.is_master_process')
    def test_client_uses_sync_mode_when_master_process(self, is_master_process):
        # when in the master process, the client should use the non-async
        # HTTP transport, even if async_mode is True
        is_master_process.return_value = True
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=True,
        )
        self.assertIsInstance(
            client._get_transport(urlparse.urlparse('http://exampe.com')),
            HTTPTransport
        )

    @mock.patch('opbeat.base.Client.send')
    @mock.patch('opbeat.base.RequestsStore.should_collect')
    def test_ignore_patterns(self, should_collect, mock_send):
        client = Client(
            servers=['http://example.com'],
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret',
            async_mode=True,
            transactions_ignore_patterns=[
                '^OPTIONS',
                'views.api.v2'
            ]
        )

        should_collect.return_value = False
        client.begin_transaction("web")
        client.end_transaction('OPTIONS views.healthcheck', 200)

        client.begin_transaction("web")
        client.end_transaction('GET views.users', 200)

        self.assertEqual(len(client.instrumentation_store), 1)
