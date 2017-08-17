import pytest  # isort:skip
pytest.importorskip("flask")  # isort:skip

import mock
from flask import Flask, render_template, signals

from elasticapm.contrib.flask import ElasticAPM
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


def create_app():
    app = Flask(__name__)

    @app.route('/an-error/', methods=['GET', 'POST'])
    def an_error():
        raise ValueError('hello world')

    @app.route('/users/', methods=['GET', 'POST'])
    def users():
        return render_template('users.html',
                               users=['Ron', 'Rasmus'])

    return app


class FlaskTest(TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

        self.elasticapm_client = get_tempstoreclient()
        self.elasticapm = ElasticAPM(self.app, client=self.elasticapm_client)

    def tearDown(self):
        signals.request_started.disconnect(self.elasticapm.request_started)
        signals.request_finished.disconnect(self.elasticapm.request_finished)

    def test_error_handler(self):
        response = self.client.get('/an-error/')
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.elasticapm_client.events), 1)

        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], 'ValueError: hello world')
        self.assertEquals(event['culprit'], 'tests.contrib.flask.flask_tests.an_error')

    def test_get(self):
        response = self.client.get('/an-error/?foo=bar')
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.elasticapm_client.events), 1)

        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['url']['raw'], 'http://localhost/an-error/?foo=bar')
        self.assertEquals(request['url']['search'], 'foo=bar')
        self.assertEquals(request['method'], 'GET')
        self.assertEquals(request['body'], None)
        self.assertTrue('headers' in request)
        headers = request['headers']
        self.assertTrue('content-length' in headers, headers.keys())
        self.assertEquals(headers['content-length'], '0')
        self.assertTrue('content-type' in headers, headers.keys())
        self.assertEquals(headers['content-type'], '')
        self.assertTrue('host' in headers, headers.keys())
        self.assertEquals(headers['host'], 'localhost')
        env = request['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_get_debug(self):
        self.app.config['DEBUG'] = True
        self.app.config['TESTING'] = False
        self.assertRaises(ValueError, self.app.test_client().get, '/an-error/?foo=bar')
        self.assertEquals(len(self.elasticapm_client.events), 0)

    def test_get_debug_elasticapm(self):
        self.app.config['DEBUG'] = True
        self.app.config['TESTING'] = True
        self.app.config['ELASTICAPM'] = {'DEBUG': True}
        self.assertRaises(ValueError, self.app.test_client().get, '/an-error/?foo=bar')
        self.assertEquals(len(self.elasticapm_client.events), 1)

    def test_post(self):
        response = self.client.post('/an-error/?biz=baz', data={'foo': 'bar'})
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.elasticapm_client.events), 1)

        event = self.elasticapm_client.events.pop(0)['errors'][0]

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['url']['raw'], 'http://localhost/an-error/?biz=baz')
        self.assertEquals(request['url']['search'], 'biz=baz')
        self.assertEquals(request['method'], 'POST')
        self.assertEquals(request['body'], 'foo=bar')
        self.assertTrue('headers' in request)
        headers = request['headers']
        self.assertTrue('content-length' in headers, headers.keys())
        self.assertEquals(headers['content-length'], '7')
        self.assertTrue('content-type' in headers, headers.keys())
        self.assertEquals(headers['content-type'], 'application/x-www-form-urlencoded')
        self.assertTrue('host' in headers, headers.keys())
        self.assertEquals(headers['host'], 'localhost')
        env = request['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_instrumentation(self):
        with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
            should_collect.return_value = False
            resp = self.client.post('/users/')

        assert resp.status_code == 200, resp.response

        transactions = self.elasticapm_client.instrumentation_store.get_all()

        # If the test falls right at the change from one minute to another
        # this will have two items.
        assert len(transactions) == 1
        traces = transactions[0]['traces']
        assert len(traces) == 2, [t['name'] for t in traces]

        expected_signatures = ['transaction', 'users.html']

        assert set([t['name'] for t in traces]) == set(expected_signatures)

        assert traces[1]['name'] == 'transaction'
        assert traces[1]['type'] == 'transaction'

        assert traces[0]['name'] == 'users.html'
        assert traces[0]['type'] == 'template.jinja2'

    def test_instrumentation_404(self):
        with mock.patch("elasticapm.traces.TransactionsStore.should_collect") as should_collect:
            should_collect.return_value = False
            resp = self.client.post('/no-such-page/')

        assert resp.status_code == 404, resp.response

        transactions = self.elasticapm_client.instrumentation_store.get_all()

        expected_signatures = ['transaction']

        assert len(transactions) == 1
        traces = transactions[0]['traces']
        print(transactions[0])
        assert transactions[0]['result'] == '404'
        assert len(traces) == 1, [t["signature"] for t in traces]

        assert set([t['name'] for t in traces]) == set(expected_signatures)

        assert traces[0]['name'] == 'transaction'
        assert traces[0]['type'] == 'transaction'

    def test_framework_version(self):
        elasticapm = ElasticAPM(app=self.app)
        app_info = elasticapm.client.get_app_info()
        assert 'flask' == app_info['framework']['name']
