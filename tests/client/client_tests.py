# -*- coding: utf-8 -*-
import platform
import time

import mock
import pytest

import elasticapm
from elasticapm.base import Client, ClientState
from elasticapm.transport.base import Transport, TransportException
from elasticapm.transport.http import HTTPTransport
from elasticapm.utils import compat
from elasticapm.utils.compat import urlparse


def test_client_state_should_try_online():
    state = ClientState()
    assert state.should_try() is True


def test_client_state_should_try_new_error():
    state = ClientState()
    state.status = state.ERROR
    state.last_check = time.time()
    state.retry_number = 1
    assert state.should_try() is False


def test_client_state_should_try_time_passed_error():
    state = ClientState()
    state.status = state.ERROR
    state.last_check = time.time() - 10
    state.retry_number = 1
    assert state.should_try() is True


def test_client_state_set_fail():
    state = ClientState()
    state.set_fail()
    assert state.status == state.ERROR
    assert state.last_check is not None
    assert state.retry_number == 1


def test_client_state_set_success():
    state = ClientState()
    state.status = state.ERROR
    state.last_check = 'foo'
    state.retry_number = 0
    state.set_success()
    assert state.status == state.ONLINE
    assert state.last_check is None
    assert state.retry_number == 0


class DummyTransport(Transport):
    def send(self, data, headers):
        pass


def test_app_info(elasticapm_client):
    app_info = elasticapm_client.get_app_info()
    assert app_info['name'] == elasticapm_client.config.app_name
    assert app_info['language'] == {
        'name': 'python',
        'version': platform.python_version()
    }


def test_system_info(elasticapm_client):
    system_info = elasticapm_client.get_system_info()
    assert {'hostname', 'architecture', 'platform'} == set(system_info.keys())


def test_config_by_environment():
    with mock.patch.dict('os.environ', {
        'ELASTIC_APM_APP_NAME': 'app',
        'ELASTIC_APM_SECRET_TOKEN': 'token',
    }):
        client = Client()
        assert client.config.app_name == 'app'
        assert client.config.secret_token == 'token'
        assert client.config.disable_send == False
    with mock.patch.dict('os.environ', {
        'ELASTIC_APM_DISABLE_SEND': 'true',
    }):
        client = Client()
        assert client.config.disable_send == True


def test_config_non_string_types():
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
        server='localhost',
        app_name=MyValue('bar'),
        secret_token=MyValue('bay')
    )
    assert isinstance(client.config.secret_token, compat.string_types)
    assert isinstance(client.config.app_name, compat.string_types)


def test_custom_transport():
    client = Client(
        server='localhost',
        app_name='bar',
        secret_token='baz',
        transport_class='tests.client.client_tests.DummyTransport',
    )
    assert client._transport_class == DummyTransport


def test_empty_processor_list():
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        processors=[],
    )

    assert client.processors == []

@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_sync(should_try, http_send):
    should_try.return_value = True

    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        transport_class='elasticapm.transport.http_urllib3.Urllib3Transport',
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


@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_sync_stdlib(should_try, http_send):
    should_try.return_value = True

    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        transport_class='elasticapm.transport.http_urllib3.Urllib3Transport',
    )
    logger = mock.Mock()
    client.error_logger.error = logger

    # test error
    encoded_data = client.encode({'message': 'oh no'})
    http_send.side_effect = ValueError('oopsie')
    client.send_remote('http://example.com/api/store', data=encoded_data)
    assert client.state.status == client.state.ERROR
    assert len(logger.call_args_list) == 1
    assert 'oopsie' in logger.call_args_list[0][0][1]

    # test recovery
    http_send.side_effect = None
    client.send_remote('http://example.com/api/store', 'foo')
    assert client.state.status == client.state.ONLINE


@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_async(should_try, http_send):
    should_try.return_value = True

    client = Client(
        server='http://example.com',
        app_name='app_name',
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


@mock.patch('elasticapm.base.Client.send_remote')
@mock.patch('elasticapm.base.time.time')
def test_send(time, send_remote):
    time.return_value = 1328055286.51
    public = "public"
    access_token = "secret"
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
    )
    client.send(**{
        'foo': 'bar',
    })
    send_remote.assert_called_once_with(
        url='http://example.com',
        data=compat.b('x\x9c\xabVJ\xcb\xcfW\xb2RPJJ,R\xaa\x05\x00 \x98\x04T'),
        headers={
            'Content-Type': 'application/json',
            'Content-Encoding': 'deflate',
            'Authorization': 'Bearer %s' % (access_token),
            'User-Agent': 'elasticapm-python/%s' % elasticapm.VERSION,
        },
    )


@mock.patch('elasticapm.base.Client.send_remote')
@mock.patch('elasticapm.base.time.time')
def test_send_not_enabled(time, send_remote):
    time.return_value = 1328055286.51
    with mock.patch.dict('os.environ', {'ELASTIC_APM_DISABLE_SEND': 'true'}):
        client = Client(
            server='http://example.com',
            app_name='app_name',
            secret_token='secret',
        )
    client.send(**{
        'foo': 'bar',
    })

    assert not send_remote.called


@mock.patch('elasticapm.base.Client.send_remote')
@mock.patch('elasticapm.base.time.time')
def test_send_with_auth_header(time, send_remote):
    time.return_value = 1328055286.51
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
    )
    client.send(auth_header='foo', **{
        'foo': 'bar',
    })
    send_remote.assert_called_once_with(
        url='http://example.com',
        data=compat.b('x\x9c\xabVJ\xcb\xcfW\xb2RPJJ,R\xaa\x05\x00 \x98\x04T'),
        headers={
            'Content-Type': 'application/json',
            'Content-Encoding': 'deflate',
            'Authorization': 'foo',
            'User-Agent': 'elasticapm-python/%s' % elasticapm.VERSION,
        },
    )


@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.close')
@mock.patch('elasticapm.base.Client._collect_transactions')
def test_client_shutdown_sync(mock_traces_collect, mock_close, mock_send):
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        transport_class='elasticapm.transport.http_urllib3.Urllib3Transport',
    )
    client.send(auth_header='foo', **{
        'foo': 'bar',
    })
    client.close()
    assert mock_close.call_count == 1
    assert mock_traces_collect.call_count == 1


@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.base.Client._collect_transactions')
def test_client_shutdown_async(mock_traces_collect, mock_send):
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        async_mode=True,
    )
    client.send(auth_header='foo', **{
        'foo': 'bar',
    })
    client.close()
    assert mock_traces_collect.call_count == 1
    assert mock_send.call_count == 1


def test_encode_decode(elasticapm_client):
    data = {'foo': 'bar'}
    encoded = elasticapm_client.encode(data)
    assert isinstance(encoded, compat.binary_type)
    assert data == elasticapm_client.decode(encoded)


def test_explicit_message_on_message_event(elasticapm_client):
    elasticapm_client.capture('Message', message='test', data={
        'message': 'foo'
    })

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['message'] == 'foo'


def test_explicit_message_on_exception_event(elasticapm_client):
    try:
        raise ValueError('foo')
    except ValueError:
        elasticapm_client.capture('Exception', data={'message': 'foobar'})

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['message'] == 'foobar'


def test_exception_event(elasticapm_client):
    try:
        raise ValueError('foo')
    except ValueError:
        elasticapm_client.capture('Exception')

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert 'exception' in event
    exc = event['exception']
    assert exc['message'] == 'ValueError: foo'
    assert exc['type'] == 'ValueError'
    assert exc['module'] == ValueError.__module__  # this differs in some Python versions
    assert 'stacktrace' in exc
    frames = exc['stacktrace']
    assert len(frames) == 1
    frame = frames[0]
    assert frame['abs_path'], __file__.replace('.pyc' == '.py')
    assert frame['filename'] == 'tests/client/client_tests.py'
    assert frame['module'] == __name__
    assert frame['function'] == 'test_exception_event'
    assert 'timestamp' in event
    assert 'log' not in event


def test_message_event(elasticapm_client):
    elasticapm_client.capture('Message', message='test')

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['log']['message'] == 'test'
    assert 'stacktrace' not in event
    assert 'timestamp' in event


def test_logger(elasticapm_client):
    elasticapm_client.capture('Message', message='test', data={'logger': 'test'})

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['logger'] == 'test'
    assert 'timestamp' in event


@mock.patch('elasticapm.base.Client.send')
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_metrics_collection(should_collect, mock_send):
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
    )
    should_collect.return_value = False
    for i in range(7):
        client.begin_transaction("transaction.test")
        client.end_transaction('test-transaction', 200)

    assert len(client.instrumentation_store) == 7
    assert mock_send.call_count == 0
    should_collect.return_value = True

    client.begin_transaction("transaction.test")
    client.end_transaction('my-other-transaction', 200)
    assert len(client.instrumentation_store) == 0
    assert mock_send.call_count == 1


@mock.patch('elasticapm.base.Client.send')
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_call_end_twice(should_collect, mock_send, elasticapm_client):
    should_collect.return_value = False
    elasticapm_client.begin_transaction("celery")

    elasticapm_client.end_transaction('test-transaction', 200)
    elasticapm_client.end_transaction('test-transaction', 200)


@mock.patch('elasticapm.utils.is_master_process')
def test_client_uses_sync_mode_when_master_process(is_master_process):
    # when in the master process, the client should use the non-async
    # HTTP transport, even if async_mode is True
    is_master_process.return_value = True
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        async_mode=True,
    )
    assert isinstance(
        client._get_transport(urlparse.urlparse('http://exampe.com')),
        HTTPTransport
    )


@mock.patch('elasticapm.base.Client.send')
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_ignore_patterns(should_collect, mock_send):
    client = Client(
        server='http://example.com',
        app_name='app_name',
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

    transactions = client.instrumentation_store.get_all()

    assert len(transactions) == 1
    assert transactions[0]['name'] == 'GET views.users'


@mock.patch('elasticapm.base.Client.send_remote')
def test_disable_send(mock_send_remote):
    client = Client(
        server='http://example.com',
        app_name='app_name',
        secret_token='secret',
        disable_send=True
    )

    assert client.config.disable_send

    client.capture('Message', message='test', data={'logger': 'test'})

    assert mock_send_remote.call_count == 0


def test_invalid_app_name_disables_send():
    client = Client({'APP_NAME': '@%&!'})

    assert len(client.config.errors) == 1
    assert 'APP_NAME' in client.config.errors

    assert client.config.disable_send


def test_empty_transport_disables_send():
    client = Client({'APP_NAME': 'foo', 'TRANSPORT_CLASS': None})

    assert len(client.config.errors) == 1
    assert 'TRANSPORT_CLASS' in client.config.errors

    assert client.config.disable_send


@pytest.mark.parametrize('elasticapm_client', [{'traces_send_frequency': 2}], indirect=True)
def test_send_timer(elasticapm_client):
    assert elasticapm_client._send_timer is None
    assert elasticapm_client.config.traces_send_frequency == 2
    elasticapm_client.begin_transaction('test_type')
    elasticapm_client.end_transaction('test')

    assert elasticapm_client._send_timer is not None
    assert elasticapm_client._send_timer.interval == 2
    assert elasticapm_client._send_timer.is_alive()

    elasticapm_client.close()

    assert not elasticapm_client._send_timer.is_alive()
