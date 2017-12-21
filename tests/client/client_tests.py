# -*- coding: utf-8 -*-
import platform
import time

import mock
import pytest

import elasticapm
from elasticapm.base import Client, ClientState
from elasticapm.transport.base import Transport, TransportException
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
    app_info = elasticapm_client.get_service_info()
    assert app_info['name'] == elasticapm_client.config.service_name
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
        'ELASTIC_APM_SERVICE_NAME': 'app',
        'ELASTIC_APM_SECRET_TOKEN': 'token',
    }):
        client = Client()
        assert client.config.service_name == 'app'
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
        service_name=MyValue('bar'),
        secret_token=MyValue('bay')
    )
    assert isinstance(client.config.secret_token, compat.string_types)
    assert isinstance(client.config.service_name, compat.string_types)
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
    {'transport_class': 'elasticapm.transport.http.Transport', 'async_mode': False}
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


@mock.patch('elasticapm.transport.http.Transport.send')
@mock.patch('elasticapm.base.ClientState.should_try')
def test_send_remote_failover_sync_stdlib(should_try, http_send):
    should_try.return_value = True

    client = Client(
        server_url='http://example.com',
        service_name='app_name',
        secret_token='secret',
        transport_class='elasticapm.transport.http.Transport',
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
    {'transport_class': 'elasticapm.transport.http.AsyncTransport', 'async_mode': True}
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
    {'transport_class': 'elasticapm.transport.http.Transport', 'async_mode': False}
], indirect=True)
@mock.patch('elasticapm.base.Client._collect_transactions')
def test_client_shutdown_sync(mock_traces_collect, sending_elasticapm_client):
    sending_elasticapm_client.send(sending_elasticapm_client.config.server_url, foo='bar')
    sending_elasticapm_client.close()
    assert len(sending_elasticapm_client.httpserver.requests) == 1
    assert mock_traces_collect.call_count == 1
    assert len(sending_elasticapm_client._transports) == 0


@pytest.mark.parametrize('sending_elasticapm_client', [
    {'transport_class': 'elasticapm.transport.http.AsyncTransport', 'async_mode': True}
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


def test_explicit_message_on_exception_event(elasticapm_client):
    try:
        raise ValueError('foo')
    except ValueError:
        elasticapm_client.capture('Exception', message='foobar')

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['exception']['message'] == 'foobar'


@pytest.mark.parametrize('elasticapm_client', [
    {'include_paths': ('tests',)}
], indirect=True)
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
    assert not frame['library_frame']
    assert 'timestamp' in event
    assert 'log' not in event
    # check that only frames from `tests` module are not marked as library frames
    assert all(frame['library_frame'] or frame['module'].startswith('tests')
               for frame in event['exception']['stacktrace'])


@pytest.mark.parametrize('elasticapm_client', [
    {'include_paths': ('tests',)}
], indirect=True)
def test_message_event(elasticapm_client):
    elasticapm_client.capture('Message', message='test')

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['log']['message'] == 'test'
    assert 'stacktrace' not in event
    assert 'timestamp' in event
    assert 'stacktrace' in event['log']
    # check that only frames from `tests` module are not marked as library frames
    assert all(frame['library_frame'] or frame['module'].startswith('tests') for frame in event['log']['stacktrace'])


def test_logger(elasticapm_client):
    elasticapm_client.capture('Message', message='test', logger_name='test')

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]
    assert event['log']['logger_name'] == 'test'
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


@mock.patch('elasticapm.base.is_master_process')
def test_client_uses_sync_mode_when_master_process(is_master_process):
    # when in the master process, the client should use the non-async
    # HTTP transport, even if async_mode is True
    is_master_process.return_value = True
    client = Client(
        server_url='http://example.com',
        service_name='app_name',
        secret_token='secret',
        async_mode=True,
    )
    transport = client._get_transport(urlparse.urlparse('http://exampe.com'))
    assert transport.async_mode is False


@pytest.mark.parametrize('elasticapm_client', [{'verify_server_cert': False}], indirect=True)
def test_client_disables_ssl_verification(elasticapm_client):
    assert not elasticapm_client.config.verify_server_cert
    assert not elasticapm_client._get_transport(compat.urlparse.urlparse('https://example.com'))._verify_server_cert


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


@pytest.mark.parametrize('elasticapm_client', [{'service_name': '@%&!'}], indirect=True)
def test_invalid_service_name_disables_send(elasticapm_client):
    assert len(elasticapm_client.config.errors) == 1
    assert 'SERVICE_NAME' in elasticapm_client.config.errors

    assert elasticapm_client.config.disable_send


@pytest.mark.parametrize('elasticapm_client', [{'service_name': 'foo', 'config': {'TRANSPORT_CLASS': None}}], indirect=True)
def test_empty_transport_disables_send(elasticapm_client):
    assert len(elasticapm_client.config.errors) == 1
    assert 'TRANSPORT_CLASS' in elasticapm_client.config.errors

    assert elasticapm_client.config.disable_send


@pytest.mark.parametrize('elasticapm_client', [{'transaction_send_frequency': 2}], indirect=True)
def test_send_timer(elasticapm_client):
    assert elasticapm_client._send_timer is None
    assert elasticapm_client.config.transaction_send_frequency == 2
    elasticapm_client.begin_transaction('test_type')
    elasticapm_client.end_transaction('test')

    assert elasticapm_client._send_timer is not None
    assert elasticapm_client._send_timer.interval == 2
    assert elasticapm_client._send_timer.is_alive()

    elasticapm_client.close()

    assert not elasticapm_client._send_timer.is_alive()


@pytest.mark.parametrize('elasticapm_client', [
    {'collect_local_variables': 'errors'},
    {'collect_local_variables': 'transactions'},
    {'collect_local_variables': 'all'},
    {'collect_local_variables': 'something'},
], indirect=True)
def test_collect_local_variables_errors(elasticapm_client):
    mode = elasticapm_client.config.collect_local_variables
    try:
        1 / 0
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    event = elasticapm_client.events[0]['errors'][0]
    if mode in ('errors', 'all'):
        assert 'vars' in event['exception']['stacktrace'][0], mode
    else:
        assert 'vars' not in event['exception']['stacktrace'][0], mode


@pytest.mark.parametrize('elasticapm_client', [
    {'collect_source': 'errors'},
    {'collect_source': 'transactions'},
    {'collect_source': 'all'},
    {'collect_source': 'something'},
], indirect=True)
def test_collect_source_errors(elasticapm_client):
    mode = elasticapm_client.config.collect_source
    try:
        1 / 0
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    event = elasticapm_client.events[0]['errors'][0]
    if mode in ('errors', 'all'):
        assert 'context_line' in event['exception']['stacktrace'][0], mode
        assert 'pre_context' in event['exception']['stacktrace'][0], mode
        assert 'post_context' in event['exception']['stacktrace'][0], mode
    else:
        assert 'context_line' not in event['exception']['stacktrace'][0], mode
        assert 'pre_context' not in event['exception']['stacktrace'][0], mode
        assert 'post_context' not in event['exception']['stacktrace'][0], mode


@pytest.mark.parametrize('elasticapm_client', [
    {'collect_local_variables': 'errors'},
    {'collect_local_variables': 'transactions'},
    {'collect_local_variables': 'all'},
    {'collect_local_variables': 'something'},
], indirect=True)
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_collect_local_variables_transactions(should_collect, elasticapm_client):
    should_collect.return_value = False
    mode = elasticapm_client.config.collect_local_variables
    elasticapm_client.begin_transaction('test')
    with elasticapm.capture_span('foo'):
        pass
    elasticapm_client.end_transaction('test', 'ok')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    if mode in ('transactions', 'all'):
        assert 'vars' in transaction['spans'][0]['stacktrace'][0], mode
    else:
        assert 'vars' not in transaction['spans'][0]['stacktrace'][0], mode


@pytest.mark.parametrize('elasticapm_client', [
    {'collect_source': 'errors'},
    {'collect_source': 'transactions'},
    {'collect_source': 'all'},
    {'collect_source': 'something'},
], indirect=True)
@mock.patch('elasticapm.base.TransactionsStore.should_collect')
def test_collect_source_transactions(should_collect, elasticapm_client):
    should_collect.return_value = False
    mode = elasticapm_client.config.collect_source
    elasticapm_client.begin_transaction('test')
    with elasticapm.capture_span('foo'):
        pass
    elasticapm_client.end_transaction('test', 'ok')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    if mode in ('transactions', 'all'):
        assert 'context_line' in transaction['spans'][0]['stacktrace'][0], mode
        assert 'pre_context' in transaction['spans'][0]['stacktrace'][0], mode
        assert 'post_context' in transaction['spans'][0]['stacktrace'][0], mode
    else:
        assert 'context_line' not in transaction['spans'][0]['stacktrace'][0], mode
        assert 'pre_context' not in transaction['spans'][0]['stacktrace'][0], mode
        assert 'post_context' not in transaction['spans'][0]['stacktrace'][0], mode
