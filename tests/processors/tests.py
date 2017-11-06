# -*- coding: utf-8 -*-
from __future__ import absolute_import

import mock
import pytest

from elasticapm import Client, processors
from elasticapm.utils import compat


@pytest.fixture()
def http_test_data():
    return {
        'context': {
            'request': {
                'body': 'foo=bar&password=123456&the_secret=abc&cc=1234567890098765',
                'env': {
                    'foo': 'bar',
                    'password': 'hello',
                    'the_secret': 'hello',
                    'a_password_here': 'hello',
                },
                'headers': {
                    'foo': 'bar',
                    'password': 'hello',
                    'the_secret': 'hello',
                    'a_password_here': 'hello',
                },
                'cookies': {
                    'foo': 'bar',
                    'password': 'topsecret',
                    'the_secret': 'topsecret',
                    'sessionid': '123',
                    'a_password_here': '123456',
                },
                'url': {
                    'raw': 'http://example.com/bla?foo=bar&password=123456&the_secret=abc&cc=1234567890098765',
                    'search': 'foo=bar&password=123456&the_secret=abc&cc=1234567890098765'
                }
            },
            'response': {
                'status_code': '200',
                'headers': {
                    'foo': 'bar',
                    'password': 'hello',
                    'the_secret': 'hello',
                    'a_password_here': 'hello',
                }
            }
        }
    }


def test_stacktrace():
    data = {
        'exception': {
            'stacktrace': [
                {
                    'vars': {
                        'foo': 'bar',
                        'password': 'hello',
                        'the_secret': 'hello',
                        'a_password_here': 'hello',
                    },
                }
            ]
        }
    }

    result = processors.sanitize_stacktrace_locals(None, data)

    assert 'stacktrace' in result['exception']
    stack = result['exception']['stacktrace']
    assert len(stack) == 1
    frame = stack[0]
    assert 'vars' in frame
    vars = frame['vars']
    assert 'foo' in vars
    assert vars['foo'] == 'bar'
    assert 'password' in vars
    assert vars['password'] == processors.MASK
    assert 'the_secret' in vars
    assert vars['the_secret'] == processors.MASK
    assert 'a_password_here' in vars
    assert vars['a_password_here'] == processors.MASK


def test_remove_http_request_body(http_test_data):
    assert 'body' in http_test_data['context']['request']

    result = processors.remove_http_request_body(None, http_test_data)

    assert 'body' not in result['context']['request']


def test_sanitize_http_request_cookies(http_test_data):
    http_test_data['context']['request']['headers']['cookie'] =\
        'foo=bar; password=12345; the_secret=12345; csrftoken=abc'

    result = processors.sanitize_http_request_cookies(None, http_test_data)

    assert result['context']['request']['cookies'] == {
        'foo': 'bar',
        'password': processors.MASK,
        'the_secret': processors.MASK,
        'sessionid': processors.MASK,
        'a_password_here': processors.MASK,
    }

    assert (result['context']['request']['headers']['cookie'] ==
            'foo=bar; password={0}; the_secret={0}; csrftoken={0}'.format(processors.MASK))


def test_sanitize_http_headers(http_test_data):
    result = processors.sanitize_http_headers(None, http_test_data)
    expected = {
        'foo': 'bar',
        'password': processors.MASK,
        'the_secret': processors.MASK,
        'a_password_here': processors.MASK,
    }
    assert result['context']['request']['headers'] == expected
    assert result['context']['response']['headers'] == expected


def test_sanitize_http_wgi_env(http_test_data):
    result = processors.sanitize_http_wsgi_env(None, http_test_data)

    assert result['context']['request']['env'] == {
        'foo': 'bar',
        'password': processors.MASK,
        'the_secret': processors.MASK,
        'a_password_here': processors.MASK,
    }


def test_sanitize_http_query_string(http_test_data):
    result = processors.sanitize_http_request_querystring(None, http_test_data)

    expected = 'foo=bar&password={0}&the_secret={0}&cc={0}'.format(
        processors.MASK
    )
    assert result['context']['request']['url']['search'] == expected
    assert result['context']['request']['url']['raw'].endswith(expected)


def test_post_as_string(http_test_data):
    result = processors.sanitize_http_request_body(None, http_test_data)
    expected = 'foo=bar&password={0}&the_secret={0}&cc={0}'.format(
        processors.MASK
    )
    assert result['context']['request']['body'] == expected


def test_querystring_as_string_with_partials(http_test_data):
    http_test_data['context']['request']['url']['search'] = 'foo=bar&password&secret=123456'
    result = processors.sanitize_http_request_querystring(None, http_test_data)

    assert (result['context']['request']['url']['search'] ==
            'foo=bar&password&secret={0}'.format(processors.MASK))


def test_sanitize_credit_card():
    result = processors._sanitize('foo', '4242424242424242')
    assert result == processors.MASK

def test_sanitize_credit_card_with_spaces():
    result = processors._sanitize('foo', '4242 4242 4242 4242')
    assert result == processors.MASK


def test_non_utf8_encoding(http_test_data):
    broken = compat.b('broken=') + u"aéöüa".encode('latin-1')
    http_test_data['context']['request']['url']['search'] = broken
    result = processors.sanitize_http_request_querystring(None, http_test_data)
    assert result['context']['request']['url']['search'] == u'broken=a\ufffd\ufffd\ufffda'


def test_remove_stacktrace_locals():
    data = {
        'exception': {
            'stacktrace': [
                {
                    'vars': {
                        'foo': 'bar',
                        'password': 'hello',
                        'the_secret': 'hello',
                        'a_password_here': 'hello',
                    },
                }
            ]
        }
    }
    result = processors.remove_stacktrace_locals(None, data)

    assert 'stacktrace' in result['exception']
    stack = result['exception']['stacktrace']
    for frame in stack:
        assert 'vars' not in frame


def test_mark_in_app_frames():
    data = {
        'exception': {
            'stacktrace': [
                {'module': 'foo'},
                {'module': 'foo.bar'},
                {'module': 'foo.bar.baz'},
                {'module': 'foobar'},
                {'module': 'foo.bar.bazzinga'},
                {'module': None},
            ]
        }
    }

    client = Client(include_paths=['foo'], exclude_paths=['foo.bar.baz'])
    data = processors.mark_in_app_frames(client, data)
    frames = data['exception']['stacktrace']

    assert frames[0]['in_app']
    assert frames[1]['in_app']
    assert not frames[2]['in_app']
    assert not frames[3]['in_app']
    assert frames[4]['in_app']
    assert not frames[5]['in_app']


def dummy_processor(client, data):
    data['processed'] = True
    return data


@pytest.mark.parametrize('elasticapm_client', [{'processors': 'tests.processors.tests.dummy_processor'}], indirect=True)
def test_transactions_processing(elasticapm_client):
    for i in range(5):
        elasticapm_client.begin_transaction('dummy')
        elasticapm_client.end_transaction('dummy_transaction', 'success')
    elasticapm_client._collect_transactions()
    for transaction in elasticapm_client.events[0]['transactions']:
        assert transaction['processed'] is True


@pytest.mark.parametrize('elasticapm_client', [{'processors': 'tests.processors.tests.dummy_processor'}], indirect=True)
def test_exception_processing(elasticapm_client):
    try:
        1 / 0
    except ZeroDivisionError:
        elasticapm_client.capture_exception()
    assert elasticapm_client.events[0]['errors'][0]['processed'] is True


@pytest.mark.parametrize('elasticapm_client', [{'processors': 'tests.processors.tests.dummy_processor'}], indirect=True)
def test_message_processing(elasticapm_client):
    elasticapm_client.capture_message('foo')
    assert elasticapm_client.events[0]['errors'][0]['processed'] is True
