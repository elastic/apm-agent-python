#  BSD 3-Clause License
#
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
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from functools import partial

from django.apps import AppConfig
from django.conf import settings as django_settings

from elasticapm.conf import constants
from elasticapm.contrib.django.client import get_client
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger
from elasticapm.utils.wsgi import get_current_url

logger = get_logger("elasticapm.traces")

ERROR_DISPATCH_UID = "elasticapm-exceptions"
REQUEST_START_DISPATCH_UID = "elasticapm-request-start"
REQUEST_FINISH_DISPATCH_UID = "elasticapm-request-stop"

MIDDLEWARE_NAME = "elasticapm.contrib.django.middleware.TracingMiddleware"

TRACEPARENT_HEADER_NAME_WSGI = "HTTP_" + constants.TRACEPARENT_HEADER_NAME.upper().replace("-", "_")
TRACEPARENT_LEGACY_HEADER_NAME_WSGI = "HTTP_" + constants.TRACEPARENT_LEGACY_HEADER_NAME.upper().replace("-", "_")
TRACESTATE_HEADER_NAME_WSGI = "HTTP_" + constants.TRACESTATE_HEADER_NAME.upper().replace("-", "_")


class ElasticAPMConfig(AppConfig):
    name = "elasticapm.contrib.django"
    label = "elasticapm.contrib.django"
    verbose_name = "ElasticAPM"

    def __init__(self, *args, **kwargs):
        super(ElasticAPMConfig, self).__init__(*args, **kwargs)
        self.client = None

    def ready(self):
        self.client = get_client()
        if self.client.config.autoinsert_django_middleware:
            self.insert_middleware(django_settings)
        register_handlers(self.client)
        if self.client.config.instrument and self.client.config.enabled:
            instrument(self.client)
        else:
            self.client.logger.debug("Skipping instrumentation. INSTRUMENT is set to False.")

    @staticmethod
    def insert_middleware(settings):
        if hasattr(settings, "MIDDLEWARE"):
            middleware_list = settings.MIDDLEWARE
            middleware_attr = "MIDDLEWARE"
        elif hasattr(settings, "MIDDLEWARE_CLASSES"):  # can be removed when we drop support for Django 1.x
            middleware_list = settings.MIDDLEWARE_CLASSES
            middleware_attr = "MIDDLEWARE_CLASSES"
        else:
            logger.debug("Could not find middleware setting, not autoinserting tracing middleware")
            return
        is_tuple = isinstance(middleware_list, tuple)
        if is_tuple:
            middleware_list = list(middleware_list)
        elif not isinstance(middleware_list, list):
            logger.debug("%s setting is not of type list or tuple, not autoinserting tracing middleware")
            return
        if middleware_list is not None and MIDDLEWARE_NAME not in middleware_list:
            logger.debug("Inserting tracing middleware into settings.%s", middleware_attr)
            middleware_list.insert(0, MIDDLEWARE_NAME)
        if is_tuple:
            middleware_list = tuple(middleware_list)
        if middleware_list:
            setattr(settings, middleware_attr, middleware_list)


def register_handlers(client):
    from django.core.signals import got_request_exception, request_finished, request_started

    from elasticapm.contrib.django.handlers import exception_handler

    # Connect to Django's internal signal handlers
    got_request_exception.disconnect(dispatch_uid=ERROR_DISPATCH_UID)
    got_request_exception.connect(partial(exception_handler, client), dispatch_uid=ERROR_DISPATCH_UID, weak=False)

    request_started.disconnect(dispatch_uid=REQUEST_START_DISPATCH_UID)
    request_started.connect(
        partial(_request_started_handler, client), dispatch_uid=REQUEST_START_DISPATCH_UID, weak=False
    )

    request_finished.disconnect(dispatch_uid=REQUEST_FINISH_DISPATCH_UID)
    request_finished.connect(
        lambda sender, **kwargs: client.end_transaction() if _should_start_transaction(client) else None,
        dispatch_uid=REQUEST_FINISH_DISPATCH_UID,
        weak=False,
    )

    # If we can import celery, register ourselves as exception handler
    try:
        import celery  # noqa F401

        from elasticapm.contrib.celery import register_exception_tracking

        try:
            register_exception_tracking(client)
        except Exception as e:
            client.logger.exception("Failed installing django-celery hook: %s" % e)
    except ImportError:
        client.logger.debug("Not instrumenting Celery, couldn't import")


def _request_started_handler(client, sender, *args, **kwargs):
    if not _should_start_transaction(client):
        return
    # try to find trace id
    trace_parent = None
    if "environ" in kwargs:
        url = get_current_url(kwargs["environ"], strip_querystring=True, path_only=True)
        if client.should_ignore_url(url):
            logger.debug("Ignoring request due to %s matching transaction_ignore_urls")
            return
        trace_parent = TraceParent.from_headers(
            kwargs["environ"],
            TRACEPARENT_HEADER_NAME_WSGI,
            TRACEPARENT_LEGACY_HEADER_NAME_WSGI,
            TRACESTATE_HEADER_NAME_WSGI,
        )
    elif "scope" in kwargs:
        scope = kwargs["scope"]
        fake_environ = {"SCRIPT_NAME": scope.get("root_path", ""), "PATH_INFO": scope["path"], "QUERY_STRING": ""}
        url = get_current_url(fake_environ, strip_querystring=True, path_only=True)
        if client.should_ignore_url(url):
            logger.debug("Ignoring request due to %s matching transaction_ignore_urls")
            return
        if "headers" in scope:
            trace_parent = TraceParent.from_headers(scope["headers"])
    client.begin_transaction("request", trace_parent=trace_parent)


def instrument(client):
    """
    Auto-instruments code to get nice spans
    """
    from elasticapm.instrumentation.control import instrument

    instrument()
    try:
        import celery  # noqa F401

        from elasticapm.contrib.celery import register_instrumentation

        register_instrumentation(client)
    except ImportError:
        client.logger.debug("Not instrumenting Celery, couldn't import")


def _should_start_transaction(client):
    middleware_attr = "MIDDLEWARE" if getattr(django_settings, "MIDDLEWARE", None) is not None else "MIDDLEWARE_CLASSES"
    middleware = getattr(django_settings, middleware_attr)
    return (
        (not django_settings.DEBUG or client.config.debug)
        and middleware
        and "elasticapm.contrib.django.middleware.TracingMiddleware" in middleware
    )
