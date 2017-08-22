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
import sys
import warnings

from django.conf import settings as django_settings

from elasticapm.contrib.django.client import get_client
from elasticapm.handlers.logging import LoggingHandler as BaseLoggingHandler
from elasticapm.utils import disabled_due_to_debug


class LoggingHandler(BaseLoggingHandler):
    def __init__(self):
        logging.Handler.__init__(self)

    def _get_client(self):
        from elasticapm.contrib.django.client import client

        return client

    client = property(_get_client)

    def _emit(self, record, **kwargs):
        from elasticapm.contrib.django.middleware import LogMiddleware

        # Fetch the request from a threadlocal variable, if available
        request = getattr(LogMiddleware.thread, 'request', None)
        request = getattr(record, 'request', request)

        return super(LoggingHandler, self)._emit(record, request=request, **kwargs)


def exception_handler(request=None, **kwargs):
    def actually_do_stuff(request=None, **kwargs):
        exc_info = sys.exc_info()
        client = get_client()
        try:
            if (
                disabled_due_to_debug(
                    getattr(django_settings, 'ELASTICAPM', {}),
                    django_settings.DEBUG
                ) or getattr(exc_info[1], 'skip_elasticapm', False)
            ):
                return

            client.capture('Exception', exc_info=exc_info, request=request)
        except Exception as exc:
            try:
                client.error_logger.exception(u'Unable to process log entry: %s' % (exc,))
            except Exception as exc:
                warnings.warn(u'Unable to process log entry: %s' % (exc,))
        finally:
            try:
                del exc_info
            except Exception as e:
                client.error_logger.exception(e)

    return actually_do_stuff(request, **kwargs)
