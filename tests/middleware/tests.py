from __future__ import absolute_import

import webob

from elasticapm.middleware import ElasticAPM
from tests.utils.compat import TestCase

from ..helpers import get_tempstoreclient


def example_app(environ, start_response):
    raise ValueError('hello world')


class MiddlewareTest(TestCase):
    def setUp(self):
        self.app = example_app

    def test_error_handler(self):
        client = get_tempstoreclient()
        middleware = ElasticAPM(self.app, client=client)

        request = webob.Request.blank('/an-error?foo=bar')
        response = middleware(request.environ, lambda *args: None)

        with self.assertRaises(ValueError):
            list(response)

        self.assertEquals(len(client.events), 1)
        event = client.events.pop(0)['errors'][0]

        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], 'ValueError: hello world')

        self.assertTrue('request' in event['context'])
        request = event['context']['request']
        self.assertEquals(request['url']['raw'], 'http://localhost/an-error?foo=bar')
        self.assertEquals(request['url']['search'], 'foo=bar')
        self.assertEquals(request['method'], 'GET')
        headers = request['headers']
        self.assertTrue('host' in headers, headers.keys())
        self.assertEquals(headers['host'], 'localhost:80')
        env = request['env']
        self.assertTrue('SERVER_NAME' in env, env.keys())
        self.assertEquals(env['SERVER_NAME'], 'localhost')
        self.assertTrue('SERVER_PORT' in env, env.keys())
        self.assertEquals(env['SERVER_PORT'], '80')
