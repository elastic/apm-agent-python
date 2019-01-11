from __future__ import absolute_import

from elasticapm.contrib.pylons import ElasticAPM


def example_app(environ, start_response):
    raise ValueError("hello world")


def test_init():
    config = {
        "elasticapm.server_url": "http://localhost/api/store",
        "elasticapm.service_name": "p" * 32,
        "elasticapm.secret_token": "a" * 32,
        "elasticapm.metrics_interval": "0ms",
    }
    middleware = ElasticAPM(example_app, config)
    assert middleware.client.config.server_url == "http://localhost/api/store"
    assert middleware.client.config.service_name == "p" * 32
    assert middleware.client.config.secret_token == "a" * 32
    assert middleware.client.config.metrics_interval == 0
