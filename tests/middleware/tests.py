from __future__ import absolute_import

import webob

from opbeat.middleware import Opbeat
from tests.utils.compat import TestCase

from ..helpers import get_tempstoreclient


def example_app(environ, start_response):
    raise ValueError('hello world')


class MiddlewareTest(TestCase):
    def setUp(self):
        self.app = example_app

    def test_error_handler(self):
        client = get_tempstoreclient()
        middleware = Opbeat(self.app, client=client)

        request = webob.Request.blank('/an-error?foo=bar')
        response = middleware(request.environ, lambda *args: None)

        with self.assertRaises(ValueError):
            list(response)

        self.assertEquals(len(client.events), 1)
        event = client.events.pop(0)

        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], 'hello world')
        self.assertEquals(event['level'], "error")
        self.assertEquals(event['message'], 'ValueError: hello world')

        self.assertTrue('http' in event)
        http = event['http']
        self.assertEquals(http['url'], 'http://localhost/an-error')
        self.assertEquals(http['query_string'], 'foo=bar')
        self.assertEquals(http['method'], 'GET')
        headers = http['headers']
        self.assertTrue('Host' in headers, headers.keys())
        self.assertEquals(headers['Host'], 'localhost:80')
        env = http['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')
