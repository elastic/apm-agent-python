# -*- coding: utf-8 -*-
from __future__ import absolute_import

from elasticapm import processors
from elasticapm.utils import six
from tests.utils.compat import TestCase


class SanitizePasswordsProcessorTest(TestCase):
    def setUp(self):
        self.http_test_data = {
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
                }
            }
        }

    def test_stacktrace(self):
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

        self.assertTrue('stacktrace' in result['exception'])
        stack = result['exception']['stacktrace']
        self.assertEquals(len(stack), 1)
        frame = stack[0]
        self.assertTrue('vars' in frame)
        vars = frame['vars']
        self.assertTrue('foo' in vars)
        self.assertEquals(vars['foo'], 'bar')
        self.assertTrue('password' in vars)
        self.assertEquals(vars['password'], processors.MASK)
        self.assertTrue('the_secret' in vars)
        self.assertEquals(vars['the_secret'], processors.MASK)
        self.assertTrue('a_password_here' in vars)
        self.assertEquals(vars['a_password_here'], processors.MASK)

    def test_remove_http_request_body(self):
        assert 'body' in self.http_test_data['context']['request']

        result = processors.remove_http_request_body(None, self.http_test_data)

        assert 'body' not in result['context']['request']

    def test_sanitize_http_request_cookies(self):
        self.http_test_data['context']['request']['headers']['cookie'] =\
            'foo=bar; password=12345; the_secret=12345; csrftoken=abc'

        result = processors.sanitize_http_request_cookies(None, self.http_test_data)

        assert result['context']['request']['cookies'] == {
            'foo': 'bar',
            'password': processors.MASK,
            'the_secret': processors.MASK,
            'sessionid': processors.MASK,
            'a_password_here': processors.MASK,
        }

        assert (result['context']['request']['headers']['cookie'] ==
                'foo=bar; password={0}; the_secret={0}; csrftoken={0}'.format(processors.MASK))

    def test_sanitize_http_request_headers(self):
        result = processors.sanitize_http_request_headers(None, self.http_test_data)

        assert result['context']['request']['headers'] == {
            'foo': 'bar',
            'password': processors.MASK,
            'the_secret': processors.MASK,
            'a_password_here': processors.MASK,
        }

    def test_sanitize_http_wgi_env(self):
        result = processors.sanitize_http_wsgi_env(None, self.http_test_data)

        assert result['context']['request']['env'] == {
            'foo': 'bar',
            'password': processors.MASK,
            'the_secret': processors.MASK,
            'a_password_here': processors.MASK,
        }

    def test_sanitize_http_query_string(self):
        result = processors.sanitize_http_request_querystring(None, self.http_test_data)

        expected = 'foo=bar&password={0}&the_secret={0}&cc={0}'.format(
            processors.MASK
        )
        assert result['context']['request']['url']['search'] == expected
        assert result['context']['request']['url']['raw'].endswith(expected)

    def test_post_as_string(self):
        result = processors.sanitize_http_request_body(None, self.http_test_data)
        expected = 'foo=bar&password={0}&the_secret={0}&cc={0}'.format(
            processors.MASK
        )
        assert result['context']['request']['body'] == expected

    def test_querystring_as_string_with_partials(self):
        self.http_test_data['context']['request']['url']['search'] = 'foo=bar&password&secret=123456'
        result = processors.sanitize_http_request_querystring(None, self.http_test_data)

        assert (result['context']['request']['url']['search'] ==
                'foo=bar&password&secret={0}'.format(processors.MASK))

    def test_sanitize_credit_card(self):
        result = processors._sanitize('foo', '4242424242424242')
        self.assertEquals(result, processors.MASK)

    def test_sanitize_credit_card_with_spaces(self):
        result = processors._sanitize('foo', '4242 4242 4242 4242')
        self.assertEquals(result, processors.MASK)

    def test_non_utf8_encoding(self):
        broken = six.b('broken=') + u"aéöüa".encode('latin-1')
        self.http_test_data['context']['request']['url']['search'] = broken
        result = processors.sanitize_http_request_querystring(None, self.http_test_data)
        assert result['context']['request']['url']['search'] == u'broken=a\ufffd\ufffd\ufffda'


def test_remove_http_request_body():
    data = {
        'context': {
            'request': {
                'body': 'foo'
            },
        }
    }

    result = processors.remove_http_request_body(None, data)

    assert 'request' in result['context']
    request = result['context']['request']
    assert 'body' not in request


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
