#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE


from __future__ import absolute_import

import logging
import sys
import warnings

from django.apps import apps
from django.conf import settings as django_settings

from elasticapm.handlers.logging import LoggingHandler as BaseLoggingHandler

logger = logging.getLogger("elasticapm.logging")


class LoggingHandler(BaseLoggingHandler):
    def __init__(self, level=logging.NOTSET):
        # skip initialization of BaseLoggingHandler
        logging.Handler.__init__(self, level=level)

    @property
    def client(self):
        try:
            app = apps.get_app_config("elasticapm.contrib.django")
            if not app.client:
                logger.warning("Can't send log message to APM server, Django apps not initialized yet")
            return app.client
        except LookupError:
            logger.warning("Can't send log message to APM server, elasticapm.contrib.django not in INSTALLED_APPS")

    def _emit(self, record, **kwargs):
        from elasticapm.contrib.django.middleware import LogMiddleware

        # Fetch the request from a threadlocal variable, if available
        request = getattr(LogMiddleware.thread, "request", None)
        request = getattr(record, "request", request)

        return super(LoggingHandler, self)._emit(record, request=request, **kwargs)


def exception_handler(client, request=None, **kwargs):
    def actually_do_stuff(request=None, **kwargs):
        exc_info = sys.exc_info()
        try:
            if (django_settings.DEBUG and not client.config.debug) or getattr(exc_info[1], "skip_elasticapm", False):
                return

            client.capture("Exception", exc_info=exc_info, request=request, handled=False)
        except Exception as exc:
            try:
                client.error_logger.exception(u"Unable to process log entry: %s" % (exc,))
            except Exception as exc:
                warnings.warn(u"Unable to process log entry: %s" % (exc,))
        finally:
            try:
                del exc_info
            except Exception as e:
                client.error_logger.exception(e)

    return actually_do_stuff(request, **kwargs)
