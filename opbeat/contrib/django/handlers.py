"""
opbeat.contrib.django.handlers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

from opbeat.handlers.logging import OpbeatHandler as BaseOpbeatHandler


class OpbeatHandler(BaseOpbeatHandler):
    def __init__(self):
        logging.Handler.__init__(self)

    def _get_client(self):
        from opbeat.contrib.django.models import client

        return client

    client = property(_get_client)

    def _emit(self, record):
        from opbeat.contrib.django.middleware import OpbeatLogMiddleware

        # Fetch the request from a threadlocal variable, if available
        request = getattr(OpbeatLogMiddleware.thread, 'request', None)
        request = getattr(record, 'request', request)

        return super(OpbeatHandler, self)._emit(record, request=request)
