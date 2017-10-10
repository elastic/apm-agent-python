from __future__ import absolute_import

from elasticapm.contrib.pylons import ElasticAPM


def example_app(environ, start_response):
    raise ValueError('hello world')


def test_init():
    config = {
        'elasticapm.server': 'http://localhost/api/store',
        'elasticapm.app_name': 'p' * 32,
        'elasticapm.secret_token': 'a' * 32,
    }
    middleware = ElasticAPM(example_app, config)
