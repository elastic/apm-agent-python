import pytest  # isort:skip
pytest.importorskip("flask")  # isort:skip

import mock

from elasticapm.contrib.flask import ElasticAPM
from tests.contrib.flask.fixtures import flask_apm_client, flask_app
from tests.fixtures import test_client


def test_error_handler(flask_apm_client):
    client = flask_apm_client.app.test_client()
    response = client.get('/an-error/')
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]

    assert 'exception' in event
    exc = event['exception']
    assert exc['type'] == 'ValueError'
    assert exc['message'] == 'ValueError: hello world'
    assert event['culprit'] == 'tests.contrib.flask.fixtures.an_error'


def test_get(flask_apm_client):
    client = flask_apm_client.app.test_client()
    response = client.get('/an-error/?foo=bar')
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['url']['raw'] == 'http://localhost/an-error/?foo=bar'
    assert request['url']['search'] == 'foo=bar'
    assert request['method'] == 'GET'
    assert request['body'] == None
    assert 'headers' in request
    headers = request['headers']
    assert 'content-length' in headers, headers.keys()
    assert headers['content-length'] == '0'
    assert 'content-type' in headers, headers.keys()
    assert headers['content-type'] == ''
    assert 'host' in headers, headers.keys()
    assert headers['host'] == 'localhost'
    env = request['env']
    assert 'SERVER_NAME' in env, env.keys()
    assert env['SERVER_NAME'] == 'localhost'
    assert 'SERVER_PORT' in env, env.keys()
    assert env['SERVER_PORT'] == '80'


def test_get_debug(flask_apm_client):
    app = flask_apm_client.app
    app.debug = True
    app.config['TESTING'] = False
    with pytest.raises(ValueError):
        app.test_client().get('/an-error/?foo=bar')
    assert len(flask_apm_client.client.events) == 0


def test_get_debug_elasticapm(flask_apm_client):
    app = flask_apm_client.app
    app.debug = True
    app.config['TESTING'] = True
    flask_apm_client.client.config.debug = True
    with pytest.raises(ValueError):
        app.test_client().get('/an-error/?foo=bar')
    assert len(flask_apm_client.client.events) == 1


def test_post(flask_apm_client):
    client = flask_apm_client.app.test_client()
    response = client.post('/an-error/?biz=baz', data={'foo': 'bar'})
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['url']['raw'] == 'http://localhost/an-error/?biz=baz'
    assert request['url']['search'] == 'biz=baz'
    assert request['method'] == 'POST'
    assert request['body'] == 'foo=bar'
    assert 'headers' in request
    headers = request['headers']
    assert 'content-length' in headers, headers.keys()
    assert headers['content-length'] == '7'
    assert 'content-type' in headers, headers.keys()
    assert headers['content-type'] == 'application/x-www-form-urlencoded'
    assert 'host' in headers, headers.keys()
    assert headers['host'] == 'localhost'
    env = request['env']
    assert 'SERVER_NAME' in env, env.keys()
    assert env['SERVER_NAME'] == 'localhost'
    assert 'SERVER_PORT' in env, env.keys()
    assert env['SERVER_PORT'] == '80'


def test_instrumentation(flask_apm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = flask_apm_client.app.test_client().post('/users/')

    assert resp.status_code == 200, resp.response

    transactions = flask_apm_client.client.instrumentation_store.get_all()

    assert len(transactions) == 1
    traces = transactions[0]['traces']
    assert len(traces) == 2, [t['name'] for t in traces]

    expected_signatures = ['transaction', 'users.html']

    assert set([t['name'] for t in traces]) == set(expected_signatures)

    assert traces[1]['name'] == 'transaction'
    assert traces[1]['type'] == 'transaction'

    assert traces[0]['name'] == 'users.html'
    assert traces[0]['type'] == 'template.jinja2'


def test_instrumentation_404(flask_apm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = flask_apm_client.app.test_client().post('/no-such-page/')

    assert resp.status_code == 404, resp.response

    transactions = flask_apm_client.client.instrumentation_store.get_all()

    expected_signatures = ['transaction']

    assert len(transactions) == 1
    traces = transactions[0]['traces']
    print(transactions[0])
    assert transactions[0]['result'] == '404'
    assert len(traces) == 1, [t["signature"] for t in traces]

    assert set([t['name'] for t in traces]) == set(expected_signatures)

    assert traces[0]['name'] == 'transaction'
    assert traces[0]['type'] == 'transaction'


def test_framework_version(flask_app):
    elasticapm = ElasticAPM(app=flask_app)
    app_info = elasticapm.client.get_app_info()
    assert 'flask' == app_info['framework']['name']
