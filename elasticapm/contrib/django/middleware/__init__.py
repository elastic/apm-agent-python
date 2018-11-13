"""
elasticapm.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging
import threading

from django.apps import apps
from django.conf import settings as django_settings

import elasticapm
from elasticapm.contrib.django.client import client, get_client
from elasticapm.utils import build_name_with_http_method_prefix, get_name_from_func, wrapt

try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module

try:
    from django.utils.deprecation import MiddlewareMixin
except ImportError:
    # no-op class for Django < 1.10
    class MiddlewareMixin(object):
        pass


def _is_ignorable_404(uri):
    """
    Returns True if the given request *shouldn't* notify the site managers.
    """
    urls = getattr(django_settings, "IGNORABLE_404_URLS", ())
    return any(pattern.search(uri) for pattern in urls)


class ElasticAPMClientMiddlewareMixin(object):
    @property
    def client(self):
        try:
            app = apps.get_app_config("elasticapm.contrib.django")
            return app.client
        except LookupError:
            return get_client()


class Catch404Middleware(MiddlewareMixin, ElasticAPMClientMiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code != 404 or _is_ignorable_404(request.get_full_path()):
            return response
        if django_settings.DEBUG and not self.client.config.debug:
            return response
        data = {"level": logging.INFO, "logger": "http404"}
        result = self.client.capture(
            "Message",
            request=request,
            param_message={"message": "Page Not Found: %s", "params": [request.build_absolute_uri()]},
            logger_name="http404",
            level=logging.INFO,
        )
        request._elasticapm = {"service_name": data.get("service_name", self.client.config.service_name), "id": result}
        return response


def get_name_from_middleware(wrapped, instance):
    name = [type(instance).__name__, wrapped.__name__]
    if type(instance).__module__:
        name = [type(instance).__module__] + name
    return ".".join(name)


def process_request_wrapper(wrapped, instance, args, kwargs):
    response = wrapped(*args, **kwargs)
    try:
        if response is not None:
            request = args[0]
            elasticapm.set_transaction_name(
                build_name_with_http_method_prefix(get_name_from_middleware(wrapped, instance), request)
            )
    finally:
        return response


def process_response_wrapper(wrapped, instance, args, kwargs):
    response = wrapped(*args, **kwargs)
    try:
        request, original_response = args
        # if there's no view_func on the request, and this middleware created
        # a new response object, it's logged as the responsible transaction
        # name
        if not hasattr(request, "_elasticapm_view_func") and response is not original_response:
            elasticapm.set_transaction_name(
                build_name_with_http_method_prefix(get_name_from_middleware(wrapped, instance), request)
            )
    finally:
        return response


class TracingMiddleware(MiddlewareMixin, ElasticAPMClientMiddlewareMixin):
    _elasticapm_instrumented = False
    _instrumenting_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super(TracingMiddleware, self).__init__(*args, **kwargs)
        if not self._elasticapm_instrumented:
            with self._instrumenting_lock:
                if not self._elasticapm_instrumented:
                    if self.client.config.instrument_django_middleware:
                        self.instrument_middlewares()

                    TracingMiddleware._elasticapm_instrumented = True

    def instrument_middlewares(self):
        middlewares = getattr(django_settings, "MIDDLEWARE", None) or getattr(
            django_settings, "MIDDLEWARE_CLASSES", None
        )
        if middlewares:
            for middleware_path in middlewares:
                module_path, class_name = middleware_path.rsplit(".", 1)
                try:
                    module = import_module(module_path)
                    middleware_class = getattr(module, class_name)
                    if middleware_class == type(self):
                        # don't instrument ourselves
                        continue
                    if hasattr(middleware_class, "process_request"):
                        wrapt.wrap_function_wrapper(middleware_class, "process_request", process_request_wrapper)
                    if hasattr(middleware_class, "process_response"):
                        wrapt.wrap_function_wrapper(middleware_class, "process_response", process_response_wrapper)
                except ImportError:
                    client.logger.info("Can't instrument middleware %s", middleware_path)

    def process_view(self, request, view_func, view_args, view_kwargs):
        request._elasticapm_view_func = view_func

    def process_response(self, request, response):
        if django_settings.DEBUG and not self.client.config.debug:
            return response
        try:
            if hasattr(response, "status_code"):
                if getattr(request, "_elasticapm_view_func", False):
                    transaction_name = get_name_from_func(request._elasticapm_view_func)
                    transaction_name = build_name_with_http_method_prefix(transaction_name, request)
                    elasticapm.set_transaction_name(transaction_name, override=False)

                elasticapm.set_context(
                    lambda: self.client.get_data_from_request(
                        request, capture_body=self.client.config.capture_body in ("all", "transactions")
                    ),
                    "request",
                )
                elasticapm.set_context(lambda: self.client.get_data_from_response(response), "response")
                elasticapm.set_context(lambda: self.client.get_user_info(request), "user")
                elasticapm.set_transaction_result("HTTP {}xx".format(response.status_code // 100), override=False)
        except Exception:
            self.client.error_logger.error("Exception during timing of request", exc_info=True)
        return response


class ErrorIdMiddleware(MiddlewareMixin):
    """
    Appends the X-ElasticAPM-ErrorId response header for referencing a message within
    the ElasticAPM datastore.
    """

    def process_response(self, request, response):
        if not getattr(request, "_elasticapm", None):
            return response
        response["X-ElasticAPM-ErrorId"] = request._elasticapm["id"]
        return response


class LogMiddleware(MiddlewareMixin):
    # Create a thread local variable to store the session in for logging
    thread = threading.local()

    def process_request(self, request):
        self.thread.request = request
