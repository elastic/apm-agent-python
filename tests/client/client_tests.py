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
    assert app_info['agent']['name'] == 'python'


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
        assert client.config.disable_send is False
    with mock.patch.dict('os.environ', {
        'ELASTIC_APM_DISABLE_SEND': 'true',
    }):
        client = Client()
        assert client.config.disable_send is True
    client.close()


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
        server_url='localhost',
        app_name=MyValue('bar'),
        secret_token=MyValue('bay')
    )
    assert isinstance(client.config.secret_token, compat.string_types)
    assert isinstance(client.config.app_name, compat.string_types)
    client.close()


@pytest.mark.parametrize('elasticapm_client', [
    {'transport_class': 'tests.client.client_tests.DummyTransport'}
], indirect=True)
def test_custom_transport(elasticapm_client):
    assert elasticapm_client._transport_class == DummyTransport


@pytest.mark.parametrize('elasticapm_client', [{'processors': []}], indirect=True)
def test_empty_processor_list(elasticapm_client):
    assert elasticapm_client.processors == []


@pytest.mark.parametrize('sending_elasticapm_client', [
    {'transport_class': 'elasticapm.transport.http_urllib3.Urllib3Transport', 'async_mode': False}
], indirect=True)
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_sync(should_try, sending_elasticapm_client):
    sending_elasticapm_client.httpserver.code = 400
    sending_elasticapm_client.httpserver.content = "go away"
    should_try.return_value = True

    logger = mock.Mock()
    sending_elasticapm_client.error_logger.error = logger

    # test error
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, **{'message': 'foo'})
    assert sending_elasticapm_client.state.status == sending_elasticapm_client.state.ERROR
    assert len(logger.call_args_list) == 2
    assert 'go away' in logger.call_args_list[0][0][0]
    assert 'foo' in logger.call_args_list[1][0][1]

    # test recovery
    sending_elasticapm_client.httpserver.code = 202
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, **{'message': 'foo'})
    assert sending_elasticapm_client.state.status == sending_elasticapm_client.state.ONLINE


@mock.patch('elasticapm.transport.http_urllib3.Urllib3Transport.send')
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_sync_stdlib(should_try, http_send):
    should_try.return_value = True

    client = Client(
        server_url='http://example.com',
        app_name='app_name',
        secret_token='secret',
        transport_class='elasticapm.transport.http_urllib3.Urllib3Transport',
    )
    logger = mock.Mock()
    client.error_logger.error = logger

    # test error
    http_send.side_effect = ValueError('oopsie')
    client.send('http://example.com/api/store', **{'message': 'oh no'})
    assert client.state.status == client.state.ERROR
    assert len(logger.call_args_list) == 1
    assert 'oopsie' in logger.call_args_list[0][0][1]

    # test recovery
    http_send.side_effect = None
    client.send('http://example.com/api/store', **{'message': 'oh no'})
    assert client.state.status == client.state.ONLINE
    client.close()


@pytest.mark.parametrize('sending_elasticapm_client', [
    {'transport_class': 'elasticapm.transport.http_urllib3.AsyncUrllib3Transport', 'async_mode': True}
], indirect=True)
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_async(should_try, sending_elasticapm_client):
    should_try.return_value = True
    sending_elasticapm_client.httpserver.code = 400
    logger = mock.Mock()
    sending_elasticapm_client.error_logger.error = logger

    # test error
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, **{'message': 'oh no'})
    sending_elasticapm_client.close()
    assert sending_elasticapm_client.state.status == sending_elasticapm_client.state.ERROR
    assert len(logger.call_args_list) == 2
    assert '400' in logger.call_args_list[0][0][0]
    assert 'oh no' in logger.call_args_list[1][0][1]

    # test recovery
    sending_elasticapm_client.httpserver.code = 202
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, **{'message': 'yay'})
    sending_elasticapm_client.close()
    assert sending_elasticapm_client.state.status == sending_elasticapm_client.state.ONLINE


@mock.patch('elasticapm.base.time.time')
def test_send(time, sending_elasticapm_client):
    time.return_value = 1328055286.51

    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, foo='bar')
    sending_elasticapm_client.close()
    request = sending_elasticapm_client.httpserver.requests[0]
    expected_headers = {
        'Content-Type': 'application/json',
        'Content-Encoding': 'deflate',
        'Authorization': 'Bearer %s' % sending_elasticapm_client.config.secret_token,
        'User-Agent': 'elasticapm-python/%s' % elasticapm.VERSION,
    }
    seen_headers = dict(request.headers)
    for k, v in expected_headers.items():
        assert seen_headers[k] == v

    assert request.content_length == 22


@pytest.mark.parametrize('sending_elasticapm_client', [{'disable_send': True}], indirect=True)
@mock.patch('elasticapm.base.time.time')
def test_send_not_enabled(time, sending_elasticapm_client):
    time.return_value = 1328055286.51
    assert sending_elasticapm_client.config.disable_send
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, foo='bar')
    sending_elasticapm_client.close()

    assert len(sending_elasticapm_client.httpserver.requests) == 0


@pytest.mark.parametrize('sending_elasticapm_client', [
    {'transport_class': 'elasticapm.transport.http_urllib3.Urllib3Transport', 'async_mode': False}
], indirect=True)
@mock.patch('elasticapm.base.Client._collect_transactions')
def test_client_shutdown_sync(mock_traces_collect, sending_elasticapm_client):
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, foo='bar')
    sending_elasticapm_client.close()
    assert len(sending_elasticapm_client.httpserver.requests) == 1
    assert mock_traces_collect.call_count == 1
    assert len(sending_elasticapm_client._transports) == 0


@pytest.mark.parametrize('sending_elasticapm_client', [
    {'transport_class': 'elasticapm.transport.http_urllib3.AsyncUrllib3Transport', 'async_mode': True}
], indirect=True)
@mock.patch('elasticapm.base.Client._collect_transactions')
def test_client_shutdown_async(mock_traces_collect, sending_elasticapm_client):
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, foo='bar')
    sending_elasticapm_client.close()
    assert mock_traces_collect.call_count == 1
    assert len(sending_elasticapm_client.httpserver.requests) == 1
    assert len(sending_elasticapm_client._transports) == 0


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


@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_metrics_collection(should_collect, sending_elasticapm_client):
    should_collect.return_value = False
    for i in range(7):
        sending_elasticapm_client.begin_transaction("transaction.test")
        sending_elasticapm_client.end_transaction('test-transaction', 200)

    assert len(sending_elasticapm_client.instrumentation_store) == 7
    assert len(sending_elasticapm_client.httpserver.requests) == 0
    should_collect.return_value = True

    sending_elasticapm_client.begin_transaction("transaction.test")
    sending_elasticapm_client.end_transaction('my-other-transaction', 200)
    assert len(sending_elasticapm_client.httpserver.requests) == 1


@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_call_end_twice(should_collect, elasticapm_client):
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
        server_url='http://example.com',
        app_name='app_name',
        secret_token='secret',
        async_mode=True,
    )
    assert isinstance(
        client._get_transport(urlparse.urlparse('http://exampe.com')),
        HTTPTransport
    )


@pytest.mark.parametrize('elasticapm_client', [{'transactions_ignore_patterns': [
        '^OPTIONS',
        'views.api.v2'
    ]}], indirect=True)
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_ignore_patterns(should_collect, elasticapm_client):
    should_collect.return_value = False
    elasticapm_client.begin_transaction("web")
    elasticapm_client.end_transaction('OPTIONS views.healthcheck', 200)

    elasticapm_client.begin_transaction("web")
    elasticapm_client.end_transaction('GET views.users', 200)

    transactions = elasticapm_client.instrumentation_store.get_all()

    assert len(transactions) == 1
    assert transactions[0]['name'] == 'GET views.users'


@pytest.mark.parametrize('sending_elasticapm_client', [{'disable_send': True}], indirect=True)
def test_disable_send(sending_elasticapm_client):
    assert sending_elasticapm_client.config.disable_send

    sending_elasticapm_client.capture('Message', message='test', data={'logger': 'test'})

    assert len(sending_elasticapm_client.httpserver.requests) == 0


@pytest.mark.parametrize('elasticapm_client', [{'app_name': '@%&!'}], indirect=True)
def test_invalid_app_name_disables_send(elasticapm_client):
    assert len(elasticapm_client.config.errors) == 1
    assert 'APP_NAME' in elasticapm_client.config.errors

    assert elasticapm_client.config.disable_send


@pytest.mark.parametrize('elasticapm_client', [{'app_name': 'foo', 'config': {'TRANSPORT_CLASS': None}}], indirect=True)
def test_empty_transport_disables_send(elasticapm_client):
    assert len(elasticapm_client.config.errors) == 1
    assert 'TRANSPORT_CLASS' in elasticapm_client.config.errors

    assert elasticapm_client.config.disable_send


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
