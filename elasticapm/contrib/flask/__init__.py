"""
elasticapm.contrib.flask
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

import flask
from flask import request, signals

import elasticapm.instrumentation.control
from elasticapm.base import Client
from elasticapm.conf import setup_logging
from elasticapm.contrib.flask.utils import (get_data_from_request,
                                            get_data_from_response)
from elasticapm.handlers.logging import LoggingHandler
from elasticapm.utils import build_name_with_http_method_prefix

logger = logging.getLogger('elasticapm.errors.client')


def make_client(client_cls, app, **defaults):
    config = app.config.get('ELASTIC_APM', {})

    defaults.setdefault('include_paths', {app.import_name})
    if 'framework_name' not in defaults:
        defaults['framework_name'] = 'flask'
        defaults['framework_version'] = getattr(flask, '__version__', '<0.7')

    client = client_cls(config, **defaults)
    return client


class ElasticAPM(object):
    """
    Flask application for Elastic APM.

    Look up configuration from ``os.environ.get('ELASTIC_APM_APP_NAME')`` and
    ``os.environ.get('ELASTIC_APM_SECRET_TOKEN')``::

    >>> elasticapm = ElasticAPM(app)

    Pass an arbitrary APP_NAME and SECRET_TOKEN::

    >>> elasticapm = ElasticAPM(app, app_name='myapp', secret_token='asdasdasd')

    Pass an explicit client::

    >>> elasticapm = ElasticAPM(app, client=client)

    Automatically configure logging::

    >>> elasticapm = ElasticAPM(app, logging=True)

    Capture an exception::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     elasticapm.capture_exception()

    Capture a message::

    >>> elasticapm.capture_message('hello, world!')
    """
    def __init__(self, app=None, client=None, client_cls=Client, logging=False, **defaults):
        self.app = app
        self.logging = logging
        self.client_cls = client_cls
        self.client = client

        if app:
            self.init_app(app, **defaults)

    def handle_exception(self, *args, **kwargs):
        if not self.client:
            return

        if self.app.debug and not self.client.config.debug:
            return

        self.client.capture(
            'Exception', exc_info=kwargs.get('exc_info'),
            data={'context': {'request': get_data_from_request(request)}},
            extra={
                'app': self.app,
            },
        )

    def init_app(self, app, **defaults):
        self.app = app
        if not self.client:
            self.client = make_client(self.client_cls, app, **defaults)

        if self.logging:
            setup_logging(LoggingHandler(self.client))

        signals.got_request_exception.connect(self.handle_exception, sender=app, weak=False)

        try:
            from elasticapm.contrib.celery import register_exception_tracking
            register_exception_tracking(self.client)
        except ImportError:
            pass

        # Instrument to get traces
        if self.client.config.disable_instrumentation:
            logger.debug("Skipping instrumentation. DISABLE_INSTRUMENTATION is set.")
        else:
            elasticapm.instrumentation.control.instrument()

            signals.request_started.connect(self.request_started, sender=app)
            signals.request_finished.connect(self.request_finished, sender=app)
            try:
                from elasticapm.contrib.celery import register_instrumentation
                register_instrumentation(self.client)
            except ImportError:
                pass

    def request_started(self, app):
        if not (self.app.debug and not self.client.config.debug):
            self.client.begin_transaction("request")

    def request_finished(self, app, response):
        rule = request.url_rule.rule if request.url_rule is not None else ""
        rule = build_name_with_http_method_prefix(rule, request)
        request_data = get_data_from_request(request)
        response_data = get_data_from_response(response)
        self.client.set_transaction_extra_data(request_data, 'request')
        self.client.set_transaction_extra_data(response_data, 'response')
        if response.status_code:
            result = 'HTTP {}xx'.format(response.status_code // 100)
        else:
            result = response.status
        self.client.end_transaction(rule, result)

    def capture_exception(self, *args, **kwargs):
        assert self.client, 'capture_exception called before application configured'
        return self.client.capture_exception(*args, **kwargs)

    def capture_message(self, *args, **kwargs):
        assert self.client, 'capture_message called before application configured'
        return self.client.capture_message(*args, **kwargs)
