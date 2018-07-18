"""
elasticapm.middleware
~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

import sys

from elasticapm.utils import get_url_dict
from elasticapm.utils.wsgi import get_current_url, get_environ, get_headers


class ElasticAPM(object):
    """
    A WSGI middleware which will attempt to capture any
    uncaught exceptions and send them to ElasticAPM.

    >>> from elasticapm.base import Client
    >>> application = ElasticAPM(application, Client())
    """

    def __init__(self, application, client):
        self.application = application
        self.client = client

    def __call__(self, environ, start_response):
        try:
            for event in self.application(environ, start_response):
                yield event
        except Exception:
            exc_info = sys.exc_info()
            self.handle_exception(exc_info, environ)
            exc_info = None
            raise

    def handle_exception(self, exc_info, environ):
        event_id = self.client.capture(
            "Exception",
            exc_info=exc_info,
            context={
                "request": {
                    "method": environ.get("REQUEST_METHOD"),
                    "url": get_url_dict(get_current_url(environ)),
                    "headers": dict(get_headers(environ)),
                    "env": dict(get_environ(environ)),
                }
            },
            handled=False,
        )
        return event_id
