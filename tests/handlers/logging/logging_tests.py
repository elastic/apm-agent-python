import logging

import pytest

from elasticapm.handlers.logging import LoggingHandler
from elasticapm.utils.stacks import iter_stack_frames


@pytest.fixture()
def logger(elasticapm_client):
    elasticapm_client.config.include_paths = ['tests', 'elasticapm']
    handler = LoggingHandler(elasticapm_client)
    logger = logging.getLogger(__name__)
    logger.handlers = []
    logger.addHandler(handler)
    logger.client = elasticapm_client
    return logger


def test_logger_basic(logger):
    logger.error('This is a test error')

    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event['log']['logger_name'] == __name__
    assert event['log']['level'] == "error"
    assert event['log']['message'] == 'This is a test error'
    assert 'stacktrace' in event['log']
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test error'


def test_logger_warning(logger):
    logger.warning('This is a test warning')
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event['log']['logger_name'] == __name__
    assert event['log']['level'] == "warning"
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test warning'


def test_logger_extra_data(logger):
    logger.info('This is a test info with a url', extra=dict(
        data=dict(
            url='http://example.com',
        ),
    ))
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event['context']['custom']['url'] == 'http://example.com'
    assert 'stacktrace' in event['log']
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test info with a url'


def test_logger_exc_info(logger):
    try:
        raise ValueError('This is a test ValueError')
    except ValueError:
        logger.info('This is a test info with an exception', exc_info=True)

    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]

    # assert event['message'] == 'This is a test info with an exception'
    assert 'exception' in event
    assert 'stacktrace' in event['exception']
    exc = event['exception']
    assert exc['type'] == 'ValueError'
    assert exc['message'] == 'ValueError: This is a test ValueError'
    assert 'param_message' in event['log']
    assert event['log']['message'] == 'This is a test info with an exception'


def test_message_params(logger):
    logger.info('This is a test of %s', 'args')
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['message'] == 'This is a test of args'
    assert event['log']['param_message'] == 'This is a test of %s'


def test_record_stack(logger):
    logger.info('This is a test of stacks', extra={'stack': True})
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    frames = event['log']['stacktrace']
    assert len(frames) != 1
    frame = frames[0]
    assert frame['module'] == __name__
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test of stacks'
    assert event['culprit'] == 'tests.handlers.logging.logging_tests.test_record_stack'
    assert event['log']['message'] == 'This is a test of stacks'


def test_no_record_stack(logger):
    logger.info('This is a test of no stacks', extra={'stack': False})
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event.get('culprit') == None
    assert event['log']['message'] == 'This is a test of no stacks'
    assert 'stacktrace' not in event['log']
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test of no stacks'


def test_no_record_stack_via_config(logger):
    logger.client.config.auto_log_stacks = False
    logger.info('This is a test of no stacks')
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event.get('culprit') == None
    assert event['log']['message'] == 'This is a test of no stacks'
    assert 'stacktrace' not in event['log']
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test of no stacks'


def test_explicit_stack(logger):
    logger.info('This is a test of stacks', extra={'stack': iter_stack_frames()})
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert 'culprit' in event, event
    assert event['culprit'] == 'tests.handlers.logging.logging_tests.test_explicit_stack'
    assert 'message' in event['log'], event
    assert event['log']['message'] == 'This is a test of stacks'
    assert 'exception' not in event
    assert 'param_message' in event['log']
    assert event['log']['param_message'] == 'This is a test of stacks'
    assert 'stacktrace' in event['log']


def test_extra_culprit(logger):
    logger.info('This is a test of stacks', extra={'culprit': 'foo.bar'})
    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]
    assert event['culprit'] == 'foo.bar'


def test_logger_exception(logger):
    try:
        raise ValueError('This is a test ValueError')
    except ValueError:
        logger.exception('This is a test with an exception', extra={'stack': True})

    assert len(logger.client.events) == 1
    event = logger.client.events.pop(0)['errors'][0]

    assert event['log']['message'] == 'This is a test with an exception'
    assert 'stacktrace' in event['log']
    assert 'exception' in event
    exc = event['exception']
    assert exc['type'] == 'ValueError'
    assert exc['message'] == 'ValueError: This is a test ValueError'
    assert 'param_message' in event['log']
    assert event['log']['message'] == 'This is a test with an exception'


def test_client_arg(elasticapm_client):
    handler = LoggingHandler(elasticapm_client)
    assert handler.client == elasticapm_client


def test_client_kwarg(elasticapm_client):
    handler = LoggingHandler(client=elasticapm_client)
    assert handler.client == elasticapm_client


def test_invalid_first_arg_type():
    with pytest.raises(ValueError):
        LoggingHandler(object)


def test_logger_setup():
    handler = LoggingHandler(server='foo', app_name='bar', secret_token='baz')
    client = handler.client
    assert client.config.server == 'foo'
    assert client.config.app_name == 'bar'
    assert client.config.secret_token == 'baz'
    assert handler.level == logging.NOTSET
