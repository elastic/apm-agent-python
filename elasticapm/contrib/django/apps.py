import logging
from functools import partial

from django.apps import AppConfig
from django.conf import settings as django_settings

from elasticapm.conf import constants
from elasticapm.contrib.django.client import get_client
from elasticapm.utils.disttracing import TraceParent

logger = logging.getLogger("elasticapm.traces")

ERROR_DISPATCH_UID = "elasticapm-exceptions"
REQUEST_START_DISPATCH_UID = "elasticapm-request-start"
REQUEST_FINISH_DISPATCH_UID = "elasticapm-request-stop"

TRACEPARENT_HEADER_NAME_WSGI = "HTTP_" + constants.TRACEPARENT_HEADER_NAME.upper().replace("-", "_")


class ElasticAPMConfig(AppConfig):
    name = "elasticapm.contrib.django"
    label = "elasticapm.contrib.django"
    verbose_name = "ElasticAPM"

    def __init__(self, *args, **kwargs):
        super(ElasticAPMConfig, self).__init__(*args, **kwargs)
        self.client = None

    def ready(self):
        self.client = get_client()
        register_handlers(self.client)
        if self.client.config.instrument:
            instrument(self.client)
        else:
            self.client.logger.debug("Skipping instrumentation. INSTRUMENT is set to False.")


def register_handlers(client):
    from django.core.signals import got_request_exception, request_started, request_finished
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
    traceparent_header = None
    if "environ" in kwargs:
        traceparent_header = kwargs["environ"].get(TRACEPARENT_HEADER_NAME_WSGI)
    elif "scope" in kwargs:
        # TODO handle Django Channels
        traceparent_header = None
    if traceparent_header:
        trace_parent = TraceParent.from_string(traceparent_header)
        logger.debug("Read traceparent header %s", traceparent_header)
    else:
        trace_parent = None
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
