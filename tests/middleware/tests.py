from __future__ import absolute_import

import pytest
import webob

from elasticapm.middleware import ElasticAPM


def example_app(environ, start_response):
    raise ValueError('hello world')


def test_error_handler(elasticapm_client):
    middleware = ElasticAPM(example_app, client=elasticapm_client)

    request = webob.Request.blank('/an-error?foo=bar')
    response = middleware(request.environ, lambda *args: None)

    with pytest.raises(ValueError):
        list(response)

    assert len(elasticapm_client.events) == 1
    event = elasticapm_client.events.pop(0)['errors'][0]

    assert 'exception' in event
    exc = event['exception']
    assert exc['type'] == 'ValueError'
    assert exc['message'] == 'ValueError: hello world'

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['url']['raw'] == 'http://localhost/an-error?foo=bar'
    assert request['url']['search'] == 'foo=bar'
    assert request['method'] == 'GET'
    headers = request['headers']
    assert 'host' in headers, headers.keys()
    assert headers['host'] == 'localhost:80'
    env = request['env']
    assert 'SERVER_NAME' in env, env.keys()
    assert env['SERVER_NAME'] == 'localhost'
    assert 'SERVER_PORT' in env, env.keys()
    assert env['SERVER_PORT'] == '80'
