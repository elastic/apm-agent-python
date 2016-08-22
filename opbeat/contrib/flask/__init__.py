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


def make_client(client_cls, app, organization_id=None, app_id=None, secret_token=None):
    opbeat_config = app.config.get('OPBEAT', {})
    # raise a warning if OPBEAT_ORGANIZATION_ID is set in the config, but not
    # ORGANIZATION_ID. Until 1.3.1, we erroneously checked only
    # OPBEAT_ORGANIZATION_ID
    if ('OPBEAT_ORGANIZATION_ID' in opbeat_config
            and 'ORGANIZATION_ID' not in opbeat_config):
        warnings.warn(
            'Please use ORGANIZATION_ID to set the opbeat '
            'organization id your configuration',
            DeprecationWarning,
        )
    # raise a warning if APP_ID is set in the environment, but not OPBEAT_APP_ID
    # Until 1.3.1, we erroneously checked only APP_ID
    if 'APP_ID' in os.environ and 'OPBEAT_APP_ID' not in os.environ:
        warnings.warn(
            'Please use OPBEAT_APP_ID to set the opbeat '
            'app id in the environment',
            DeprecationWarning,
        )
    # raise a warning if SECRET_TOKEN is set in the environment, but not
    # OPBEAT_SECRET_TOKEN. Until 1.3.1, we erroneously checked only SECRET_TOKEN
    if 'SECRET_TOKEN' in os.environ and 'OPBEAT_SECRET_TOKEN' not in os.environ:
        warnings.warn(
            'Please use OPBEAT_SECRET_TOKEN to set the opbeat secret token '
            'in the environment',
            DeprecationWarning,
        )
    if 'ASYNC' in opbeat_config:
        warnings.warn(
            'Usage of "ASYNC" configuration is deprecated. Use "ASYNC_MODE"',
            category=DeprecationWarning,
            stacklevel=2,
        )
        opbeat_config['ASYNC_MODE'] = opbeat_config['ASYNC']
    organization_id = (
        organization_id or
        opbeat_config.get('ORGANIZATION_ID') or  # config
        os.environ.get('OPBEAT_ORGANIZATION_ID') or  # environment
        opbeat_config.get('OPBEAT_ORGANIZATION_ID')  # deprecated fallback
    )
    app_id = (
        app_id or
        opbeat_config.get('APP_ID') or  # config
        os.environ.get('OPBEAT_APP_ID') or  # environment
        os.environ.get('APP_ID')  # deprecated fallback
    )
    secret_token = (
        secret_token or
        opbeat_config.get('SECRET_TOKEN') or  # config
        os.environ.get('OPBEAT_SECRET_TOKEN') or  # environment
        os.environ.get('SECRET_TOKEN')  # deprecated fallback
    )
    if hasattr(flask, '__version__'):
        framework_version = 'flask/' + flask.__version__
    else:
        framework_version = 'flask/<0.7'

    return client_cls(
        organization_id=organization_id,
        app_id=app_id,
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
        framework_version=framework_version,
    )


class Opbeat(object):
    """
    Flask application for Opbeat.

    Look up configuration from ``os.environ['OPBEAT_ORGANIZATION_ID']``,
    ``os.environ.get('OPBEAT_APP_ID')`` and
    ``os.environ.get('OPBEAT_SECRET_TOKEN')``::

    >>> opbeat = Opbeat(app)

    Pass an arbitrary ORGANIZATION_ID, APP_ID and SECRET_TOKEN::

    >>> opbeat = Opbeat(app, organization_id='1', app_id='1', secret_token='asdasdasd')

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
    def __init__(self, app=None, organization_id=None, app_id=None,
                 secret_token=None, client=None, client_cls=Client,
                 logging=False):
        self.organization_id = organization_id
        self.app_id = app_id
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
            data=get_data_from_request(request),
            extra={
                'app': self.app,
            },
        )

    def init_app(self, app):
        self.app = app
        if not self.client:
            self.client = make_client(
                self.client_cls, app, self.organization_id,
                self.app_id, self.secret_token,
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
