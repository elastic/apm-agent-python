"""
opbeat.contrib.flask
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import os

from flask import request
from flask.signals import got_request_exception
from opbeat.conf import setup_logging
from opbeat.base import Client
from opbeat.contrib.flask.utils import get_data_from_request
from opbeat.handlers.logging import OpbeatHandler


def make_client(client_cls, app, organization_id=None, app_id=None, secret_token=None):
    opbeat_config = app.config.get('OPBEAT', {})
    return client_cls(
        include_paths=set(opbeat_config.get('INCLUDE_PATHS', [])) | set([app.import_name]),
        exclude_paths=opbeat_config.get('EXCLUDE_PATHS'),
        servers=opbeat_config.get('SERVERS'),
        hostname=opbeat_config.get('HOSTNAME'),
        timeout=opbeat_config.get('TIMEOUT'),
        organization_id=organization_id or opbeat_config.get('OPBEAT_ORGANIZATION_ID') or os.environ.get('OPBEAT_ORGANIZATION_ID'),
        app_id=app_id or opbeat_config.get('APP_ID') or os.environ.get('APP_ID'),
        secret_token=secret_token or opbeat_config.get('SECRET_TOKEN') or os.environ.get('SECRET_TOKEN')
    )


class Opbeat(object):
    """
    Flask application for Opbeat.

    Look up configuration from ``os.environ['OPBEAT_ORGANIZATION_ID']``,
    ``os.environ.get('OPBEAT_APP_ID')`` and
    ``os.environ.get('OPBEAT_SECRET_TOKEN')``::

    >>> opbeat = Opbeat(app)

    Pass an arbitrary ORGANIZATION_ID, APP_ID and SECRET_TOKEN::

    >>> opbeat = Opbeat(app, organiation_id='1', app_id='1', secret_token='asdasdasd')

    Pass an explicit client::

    >>> opbeat = Opbeat(app, client=client)

    Automatically configure logging::

    >>> opbeat = Opbeat(app, logging=True)

    Capture an exception::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     opbeat.captureException()

    Capture a message::

    >>> opbeat.captureMessage('hello, world!')
    """
    def __init__(self, app=None, organization_id=None, app_id=None,
                 secret_token=None, client=None,
                 client_cls=Client, logging=False):
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

        self.client.capture('Exception', exc_info=kwargs.get('exc_info'),
            data=get_data_from_request(request),
            extra={
                'app': self.app,
            },
        )

    def init_app(self, app):
        self.app = app
        if not self.client:
            self.client = make_client(
                self.client_cls, app,
                self.organization_id, self.app_id, self.secret_token
            )

        if self.logging:
            setup_logging(OpbeatHandler(self.client))

        got_request_exception.connect(self.handle_exception, sender=app, weak=False)

    def captureException(self, *args, **kwargs):
        assert self.client, 'captureException called before application configured'
        return self.client.captureException(*args, **kwargs)

    def captureMessage(self, *args, **kwargs):
        assert self.client, 'captureMessage called before application configured'
        return self.client.captureMessage(*args, **kwargs)
