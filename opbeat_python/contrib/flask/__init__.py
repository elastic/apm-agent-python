"""
opbeat_python.contrib.flask
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
from opbeat_python.conf import setup_logging
from opbeat_python.base import Client
from opbeat_python.contrib.flask.utils import get_data_from_request
from opbeat_python.handlers.logging import SentryHandler


def make_client(client_cls, app, project_id=None, api_key=None):
    return client_cls(
        include_paths=set(app.config.get('OPBEAT_INCLUDE_PATHS', [])) | set([app.import_name]),
        exclude_paths=app.config.get('OPBEAT_EXCLUDE_PATHS'),
        servers=app.config.get('OPBEAT_SERVERS'),
        name=app.config.get('OPBEAT_NAME'),
        project_id=project_id or app.config.get('OPBEAT_PROJECT_ID') or os.environ.get('OPBEAT_PROJECT_ID'),
        api_key=api_key or app.config.get('OPBEAT_API_KEY') or os.environ.get('OPBEAT_API_KEY')
    )


class Opbeat(object):
    """
    Flask application for Opbeat.

    Look up configuration from ``os.environ['OPBEAT_PROJECT_ID']``
    and os.environ.get('OPBEAT_API_KEY')::

    >>> opbeat = Opbeat(app)

    Pass an arbitrary PROJECT_ID and API_KEY::

    >>> opbeat = Opbeat(app, project_id='1', api_key='asdasdasd')

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
    def __init__(self, app=None, project_id=None, api_key=None, client=None, client_cls=Client, logging=False):
        self.project_id = project_id
        self.api_key = api_key
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
            self.client = make_client(self.client_cls, app, self.project_id, self.api_key)

        if self.logging:
            setup_logging(SentryHandler(self.client))

        got_request_exception.connect(self.handle_exception, sender=app, weak=False)

    def captureException(self, *args, **kwargs):
        assert self.client, 'captureException called before application configured'
        return self.client.captureException(*args, **kwargs)

    def captureMessage(self, *args, **kwargs):
        assert self.client, 'captureMessage called before application configured'
        return self.client.captureMessage(*args, **kwargs)
