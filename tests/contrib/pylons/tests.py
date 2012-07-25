from unittest2 import TestCase
from opbeat_python.contrib.pylons import Sentry


def example_app(environ, start_response):
    raise ValueError('hello world')


class MiddlewareTest(TestCase):
    def setUp(self):
        self.app = example_app

    def test_init(self):
        config = {
            'sentry.servers': 'http://localhost/api/store',
            'sentry.project_id': 'p' * 32,
            'sentry.access_token': 's' * 32,
        }
        middleware = Sentry(self.app, config)
