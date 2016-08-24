import pytest  # isort:skip
pytest.importorskip("flask")  # isort:skip

import mock
from flask import Flask, render_template, signals

from opbeat.contrib.flask import Opbeat
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

        self.opbeat_client = get_tempstoreclient()
        self.opbeat = Opbeat(self.app, client=self.opbeat_client)

    def tearDown(self):
        signals.request_started.disconnect(self.opbeat.request_started)
        signals.request_finished.disconnect(self.opbeat.request_finished)

    def test_error_handler(self):
        response = self.client.get('/an-error/')
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.opbeat_client.events), 1)

        event = self.opbeat_client.events.pop(0)

        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], 'hello world')
        self.assertEquals(event['level'], "error")
        self.assertEquals(event['message'], 'ValueError: hello world')
        self.assertEquals(event['culprit'], 'tests.contrib.flask.flask_tests.an_error')

    def test_get(self):
        response = self.client.get('/an-error/?foo=bar')
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.opbeat_client.events), 1)

        event = self.opbeat_client.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['url'], 'http://localhost/an-error/')
        self.assertEquals(http['query_string'], 'foo=bar')
        self.assertEquals(http['method'], 'GET')
        self.assertEquals(http['data'], {})
        self.assertTrue('headers' in http)
        headers = http['headers']
        self.assertTrue('Content-Length' in headers, headers.keys())
        self.assertEquals(headers['Content-Length'], '0')
        self.assertTrue('Content-Type' in headers, headers.keys())
        self.assertEquals(headers['Content-Type'], '')
        self.assertTrue('Host' in headers, headers.keys())
        self.assertEquals(headers['Host'], 'localhost')
        env = http['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_get_debug(self):
        self.app.config['DEBUG'] = True
        self.app.config['TESTING'] = False
        self.assertRaises(ValueError, self.app.test_client().get, '/an-error/?foo=bar')
        self.assertEquals(len(self.opbeat_client.events), 0)

    def test_get_debug_opbeat(self):
        self.app.config['DEBUG'] = True
        self.app.config['TESTING'] = True
        self.app.config['OPBEAT'] = {'DEBUG': True}
        self.assertRaises(ValueError, self.app.test_client().get, '/an-error/?foo=bar')
        self.assertEquals(len(self.opbeat_client.events), 1)

    def test_post(self):
        response = self.client.post('/an-error/?biz=baz', data={'foo': 'bar'})
        self.assertEquals(response.status_code, 500)
        self.assertEquals(len(self.opbeat_client.events), 1)

        event = self.opbeat_client.events.pop(0)

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['url'], 'http://localhost/an-error/')
        self.assertEquals(http['query_string'], 'biz=baz')
        self.assertEquals(http['method'], 'POST')
        self.assertEquals(http['data'], {'foo': 'bar'})
        self.assertTrue('headers' in http)
        headers = http['headers']
        self.assertTrue('Content-Length' in headers, headers.keys())
        self.assertEquals(headers['Content-Length'], '7')
        self.assertTrue('Content-Type' in headers, headers.keys())
        self.assertEquals(headers['Content-Type'], 'application/x-www-form-urlencoded')
        self.assertTrue('Host' in headers, headers.keys())
        self.assertEquals(headers['Host'], 'localhost')
        env = http['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')

    def test_instrumentation(self):
        with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
            should_collect.return_value = False
            resp = self.client.post('/users/')

        assert resp.status_code == 200, resp.response

        transactions, traces = self.opbeat_client.instrumentation_store.get_all()

        # If the test falls right at the change from one minute to another
        # this will have two items.
        assert 0 < len(transactions) < 3, [t["transaction"] for t in transactions]
        assert len(traces) == 2, [t["signature"] for t in traces]

        expected_signatures = ['transaction', 'users.html']
        expected_transaction = 'POST /users/'

        assert set([t['signature'] for t in traces]) == set(expected_signatures)

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        assert traces[0]['signature'] == 'transaction'
        assert traces[0]['transaction'] == expected_transaction
        assert traces[0]['kind'] == 'transaction'

        assert traces[1]['signature'] == 'users.html'
        assert traces[1]['transaction'] == expected_transaction
        assert traces[1]['kind'] == 'template.jinja2'

    def test_instrumentation_404(self):
        with mock.patch("opbeat.traces.RequestsStore.should_collect") as should_collect:
            should_collect.return_value = False
            resp = self.client.post('/no-such-page/')

        assert resp.status_code == 404, resp.response

        transactions, traces = self.opbeat_client.instrumentation_store.get_all()

        expected_signatures = ['transaction']
        expected_transaction = ''

        # If the test falls right at the change from one minute to another
        # this will have two items.
        assert 0 < len(transactions) < 3, [t["transaction"] for t in transactions]

        assert transactions[0]['result'] == 404
        assert transactions[0]['transaction'] == expected_transaction
        assert len(traces) == 1, [t["signature"] for t in traces]

        assert set([t['signature'] for t in traces]) == set(expected_signatures)

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        assert traces[0]['signature'] == 'transaction'
        assert traces[0]['transaction'] == expected_transaction
        assert traces[0]['kind'] == 'transaction'

    def test_framework_version(self):
        opbeat = Opbeat(app=self.app)
        self.assertIn('framework=flask', opbeat.client.get_platform_info())
