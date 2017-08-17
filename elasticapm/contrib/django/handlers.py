"""
elasticapm.contrib.django.handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

from elasticapm.handlers.logging import LoggingHandler as BaseLoggingHandler


class LoggingHandler(BaseLoggingHandler):
    def __init__(self):
        logging.Handler.__init__(self)

    def _get_client(self):
        from elasticapm.contrib.django.models import client

        return client

    client = property(_get_client)

    def _emit(self, record):
        from elasticapm.contrib.django.middleware import LogMiddleware

        # Fetch the request from a threadlocal variable, if available
        request = getattr(LogMiddleware.thread, 'request', None)
        request = getattr(record, 'request', request)

        return super(LoggingHandler, self)._emit(record, request=request)
