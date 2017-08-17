"""
opbeat.contrib.flask
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging
import os
import warnings

import flask
from flask import request, signals

import opbeat.instrumentation.control
from opbeat.base import Client
from opbeat.conf import setup_logging
from opbeat.contrib.flask.utils import get_data_from_request
from opbeat.handlers.logging import OpbeatHandler
from opbeat.utils import (build_name_with_http_method_prefix,
                          disabled_due_to_debug)
from opbeat.utils.deprecation import deprecated

logger = logging.getLogger('opbeat.errors.client')


def make_client(client_cls, app, app_name=None, secret_token=None):
    opbeat_config = app.config.get('OPBEAT', {})
    app_name = (
        app_name or
        opbeat_config.get('APP_NAME') or  # config
        os.environ.get('OPBEAT_APP_NAME') # environment
    )
    secret_token = (
        secret_token or
        opbeat_config.get('SECRET_TOKEN') or  # config
        os.environ.get('OPBEAT_SECRET_TOKEN') # environment
    )
    if hasattr(flask, '__version__'):
        framework_version = 'flask/' + flask.__version__
    else:
        framework_version = 'flask/<0.7'

    client = client_cls(
        app_name=app_name,
        secret_token=secret_token,
        include_paths=set(opbeat_config.get('INCLUDE_PATHS', [])) | set([app.import_name]),
        exclude_paths=opbeat_config.get('EXCLUDE_PATHS'),
        filter_exception_types=opbeat_config.get('FILTER_EXCEPTION_TYPES', None),
        servers=opbeat_config.get('SERVERS'),
        transport_class=opbeat_config.get('TRANSPORT_CLASS', None),
        hostname=opbeat_config.get('HOSTNAME'),
        auto_log_stacks=opbeat_config.get('AUTO_LOG_STACKS'),
        timeout=opbeat_config.get('TIMEOUT'),
        string_max_length=opbeat_config.get('STRING_MAX_LENGTH'),
        list_max_length=opbeat_config.get('LIST_MAX_LENGTH'),
        traces_freq_send=opbeat_config.get('TRACES_FREQ_SEND'),
        processors=opbeat_config.get('PROCESSORS'),
        async_mode=opbeat_config.get('ASYNC_MODE'),
        transactions_ignore_patterns=opbeat_config.get('TRANSACTIONS_IGNORE_PATTERNS'),
    )

    client._framework = 'flask'
    client._framework_version = getattr(flask, '__version__', '<0.7')
    return client


class Opbeat(object):
    """
    Flask application for Opbeat.

    Look up configuration from ``os.environ.get('OPBEAT_APP_NAME')`` and
    ``os.environ.get('OPBEAT_SECRET_TOKEN')``::

    >>> opbeat = Opbeat(app)

    Pass an arbitrary APP_NAME and SECRET_TOKEN::

    >>> opbeat = Opbeat(app, app_name='myapp', secret_token='asdasdasd')

    Pass an explicit client::

    >>> opbeat = Opbeat(app, client=client)

    Automatically configure logging::

    >>> opbeat = Opbeat(app, logging=True)

    Capture an exception::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     opbeat.capture_exception()

    Capture a message::

    >>> opbeat.captureMessage('hello, world!')
    """
    def __init__(self, app=None, app_name=None,
                 secret_token=None, client=None, client_cls=Client,
                 logging=False):
        self.app_name = app_name
        self.secret_token = secret_token
        self.logging = logging
        self.client_cls = client_cls
        self.client = client

        if app:
            self.init_app(app)

    def handle_exception(self, *args, **kwargs):
        if not self.client:
            return

        if disabled_due_to_debug(
            self.app.config.get('OPBEAT', {}),
            self.app.config.get('DEBUG', False)
        ):
            return

        self.client.capture(
            'Exception', exc_info=kwargs.get('exc_info'),
            data={'context': {'request': get_data_from_request(request)}},
            extra={
                'app': self.app,
            },
        )

    def init_app(self, app):
        self.app = app
        if not self.client:
            self.client = make_client(
                self.client_cls,
                app,
                self.app_name,
                self.secret_token,
            )

        if self.logging:
            setup_logging(OpbeatHandler(self.client))

        signals.got_request_exception.connect(self.handle_exception, sender=app, weak=False)

        # Instrument to get traces
        skip_env_var = 'SKIP_INSTRUMENT'
        if skip_env_var in os.environ:
            logger.debug("Skipping instrumentation. %s is set.", skip_env_var)
        else:
            opbeat.instrumentation.control.instrument()

            signals.request_started.connect(self.request_started, sender=app)
            signals.request_finished.connect(self.request_finished, sender=app)

    def request_started(self, app):
        self.client.begin_transaction("web.flask")

    def request_finished(self, app, response):
        rule = request.url_rule.rule if request.url_rule is not None else ""
        rule = build_name_with_http_method_prefix(rule, request)

        self.client.end_transaction(rule, response.status_code)

    def capture_exception(self, *args, **kwargs):
        assert self.client, 'capture_exception called before application configured'
        return self.client.capture_exception(*args, **kwargs)

    def capture_message(self, *args, **kwargs):
        assert self.client, 'capture_message called before application configured'
        return self.client.capture_message(*args, **kwargs)

    @deprecated(alternative="capture_exception()")
    def captureException(self, *args, **kwargs):
        return self.capture_exception(*args, **kwargs)

    @deprecated(alternative="capture_message()")
    def captureMessage(self, *args, **kwargs):
        return self.capture_message(*args, **kwargs)
