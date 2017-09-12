from django.apps import AppConfig

from elasticapm.contrib.django.client import get_client


class ElasticAPMConfig(AppConfig):
    name = 'elasticapm.contrib.django'
    label = 'elasticapm.contrib.django'
    verbose_name = 'ElasticAPM'

    def ready(self):
        client = get_client()
        register_handlers(client)
        if not client.config.disable_instrumentation:
            instrument(client)
        else:
            client.logger.debug("Skipping instrumentation. DISABLE_INSTRUMENTATION is set.")


def register_handlers(client):
    from django.core.signals import got_request_exception
    from elasticapm.contrib.django.handlers import exception_handler

    # Connect to Django's internal signal handler
    got_request_exception.connect(exception_handler)

    # If we can import celery, register ourselves as exception handler
    try:
        import celery  # noqa F401
        from elasticapm.contrib.celery import register_exception_tracking

        try:
            register_exception_tracking(client)
        except Exception as e:
            client.logger.exception('Failed installing django-celery hook: %s' % e)
    except ImportError:
        client.logger.debug("Not instrumenting Celery, couldn't import")


def instrument(client):
    """
    Auto-instruments code to get nice traces
    """
    from elasticapm.instrumentation.control import instrument

    instrument()
    try:
        import celery  # noqa F401
        from elasticapm.contrib.celery import register_instrumentation

        register_instrumentation(client)
    except ImportError:
        client.logger.debug("Not instrumenting Celery, couldn't import")
