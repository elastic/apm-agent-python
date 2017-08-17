from __future__ import absolute_import

from elasticapm.contrib.pylons import ElasticAPM
from tests.utils.compat import TestCase


def example_app(environ, start_response):
    raise ValueError('hello world')


class MiddlewareTest(TestCase):
    def setUp(self):
        self.app = example_app

    def test_init(self):
        config = {
            'elasticapm.servers': 'http://localhost/api/store',
            'elasticapm.app_name': 'p' * 32,
            'elasticapm.secret_token': 'a' * 32,
        }
        middleware = ElasticAPM(self.app, config)
