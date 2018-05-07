import pytest  # isort:skip
pytest.importorskip("flask")  # isort:skip

import os

import mock

from elasticapm.contrib.flask import ElasticAPM
from elasticapm.utils import compat

try:
    from urllib.request import urlopen
except ImportError:
    from urllib2 import urlopen


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
    assert exc['handled'] is False
    assert event['culprit'] == 'tests.contrib.flask.fixtures.an_error'


def test_get(flask_apm_client):
    client = flask_apm_client.app.test_client()
    response = client.get('/an-error/?foo=bar')
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['url']['full'] == 'http://localhost/an-error/?foo=bar'
    assert request['url']['search'] == '?foo=bar'
    assert request['method'] == 'GET'
    assert 'body' not in request
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


@pytest.mark.parametrize('elasticapm_client', [
    {'capture_body': 'errors'},
    {'capture_body': 'all'},
    {'capture_body': 'off'},
], indirect=True)
def test_post(flask_apm_client):
    client = flask_apm_client.app.test_client()
    response = client.post('/an-error/?biz=baz', data={'foo': 'bar'})
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]

    assert 'request' in event['context']
    request = event['context']['request']
    assert request['url']['full'] == 'http://localhost/an-error/?biz=baz'
    assert request['url']['search'] == '?biz=baz'
    assert request['method'] == 'POST'
    if flask_apm_client.client.config.capture_body in ('errors', 'all'):
        assert request['body'] == {'foo': 'bar'}
    else:
        assert request['body'] == '[REDACTED]'
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


@pytest.mark.parametrize('elasticapm_client', [
    {'capture_body': 'transactions'},
    {'capture_body': 'all'},
    {'capture_body': 'off'},
], indirect=True)
def test_instrumentation(flask_apm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = flask_apm_client.app.test_client().post('/users/', data={'foo': 'bar'})
        resp.close()

    assert resp.status_code == 200, resp.response

    transactions = flask_apm_client.client.instrumentation_store.get_all()

    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction['type'] == 'request'
    assert transaction['result'] == 'HTTP 2xx'
    assert 'request' in transaction['context']
    assert transaction['context']['request']['url']['full'] == 'http://localhost/users/'
    assert transaction['context']['request']['method'] == 'POST'
    if flask_apm_client.client.config.capture_body in ('transactions', 'all'):
        assert transaction['context']['request']['body'] == {'foo': 'bar'}
    else:
        assert transaction['context']['request']['body'] == '[REDACTED]'
    assert transaction['context']['response']['status_code'] == 200
    assert transaction['context']['response']['headers'] == {
        'foo': 'bar;baz',
        'bar': 'bazzinga',
        'Content-Length': '78',
        'Content-Type': 'text/html; charset=utf-8',
    }
    spans = transactions[0]['spans']
    assert len(spans) == 1, [t['name'] for t in spans]

    expected_signatures = {'users.html'}

    assert {t['name'] for t in spans} == expected_signatures

    assert spans[0]['name'] == 'users.html'
    assert spans[0]['type'] == 'template.jinja2'


def test_instrumentation_debug(flask_apm_client):
    flask_apm_client.app.debug = True
    assert len(flask_apm_client.client.instrumentation_store) == 0
    resp = flask_apm_client.app.test_client().post('/users/', data={'foo': 'bar'})
    resp.close()
    assert len(flask_apm_client.client.instrumentation_store) == 0


@pytest.mark.parametrize('elasticapm_client', [
    {'debug': True},
], indirect=True)
def test_instrumentation_debug_client_debug(flask_apm_client):
    flask_apm_client.app.debug = True
    assert len(flask_apm_client.client.instrumentation_store) == 0
    resp = flask_apm_client.app.test_client().post('/users/', data={'foo': 'bar'})
    resp.close()
    assert len(flask_apm_client.client.instrumentation_store) == 1


def test_instrumentation_404(flask_apm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = flask_apm_client.app.test_client().post('/no-such-page/')
        resp.close()

    assert resp.status_code == 404, resp.response

    transactions = flask_apm_client.client.instrumentation_store.get_all()

    assert len(transactions) == 1
    spans = transactions[0]['spans']
    assert transactions[0]['result'] == 'HTTP 4xx'
    assert transactions[0]['context']['response']['status_code'] == 404
    assert len(spans) == 0, [t["signature"] for t in spans]


def test_non_standard_http_status(flask_apm_client):
    with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
        should_collect.return_value = False
        resp = flask_apm_client.app.test_client().get('/non-standard-status/')
        resp.close()
    assert resp.status == "0 fail", resp.response
    assert resp.status_code == 0, resp.response

    transactions = flask_apm_client.client.instrumentation_store.get_all()
    assert transactions[0]['result'] == '0 fail'  # "0" is prepended by Werkzeug BaseResponse
    assert transactions[0]['context']['response']['status_code'] == 0


def test_framework_name(flask_app):
    elasticapm = ElasticAPM(app=flask_app)
    assert elasticapm.client.config.framework_name == 'flask'
    app_info = elasticapm.client.get_service_info()
    assert app_info['framework']['name'] == 'flask'


@pytest.mark.parametrize('elasticapm_client', [
    {'capture_body': 'errors'},
    {'capture_body': 'all'},
    {'capture_body': 'off'},
], indirect=True)
def test_post_files(flask_apm_client):
    with open(os.path.abspath(__file__), mode='rb') as f:
        response = flask_apm_client.app.test_client().post('/an-error/', data={
            'foo': ['bar', 'baz'],
            'f1': (compat.BytesIO(compat.b('1')),'bla'),
            'f2': [(f, 'flask_tests.py'), (compat.BytesIO(compat.b('1')), 'blub')],
        })
    assert response.status_code == 500
    assert len(flask_apm_client.client.events) == 1

    event = flask_apm_client.client.events.pop(0)['errors'][0]
    print(flask_apm_client.client.config.capture_body)
    if flask_apm_client.client.config.capture_body in ('errors', 'all'):
        assert event['context']['request']['body'] == {
            'foo': ['bar', 'baz'],
            '_files': {
                'f1': 'bla',
                'f2': ['flask_tests.py', 'blub'],
            }
        }
    else:
        assert event['context']['request']['body'] == '[REDACTED]'


@pytest.mark.parametrize('elasticapm_client', [
    {'capture_body': 'transactions'},
], indirect=True)
def test_options_request(flask_apm_client):
    resp = flask_apm_client.app.test_client().options('/')
    resp.close()
    transactions = flask_apm_client.client.instrumentation_store.get_all()
    assert transactions[0]['context']['request']['method'] == 'OPTIONS'


def test_streaming_response(flask_apm_client):
    resp = flask_apm_client.app.test_client().get('/streaming/')
    assert resp.data == b'01234'
    resp.close()
    transaction = flask_apm_client.client.instrumentation_store.get_all()[0]
    assert transaction['duration'] > 50
    assert len(transaction['spans']) == 5


def test_response_close_wsgi(flask_wsgi_server):
    # this tests the response-close behavior using a real WSGI server
    elasticapm_client = flask_wsgi_server.app.apm_client.client
    url = flask_wsgi_server.url + '/streaming/'
    response = urlopen(url)
    response.read()
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    assert transaction['duration'] > 50
    assert len(transaction['spans']) == 5
