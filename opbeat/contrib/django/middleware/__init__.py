"""
opbeat.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging
import threading

from django.conf import settings as django_settings

from opbeat.contrib.django.models import client, get_client
from opbeat.utils import (build_name_with_http_method_prefix,
                          disabled_due_to_debug, get_name_from_func, wrapt)

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
    urls = getattr(django_settings, 'IGNORABLE_404_URLS', ())
    return any(pattern.search(uri) for pattern in urls)


class Opbeat404CatchMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if (response.status_code != 404 or
                _is_ignorable_404(request.get_full_path())):
            return response
        if disabled_due_to_debug(
                    getattr(django_settings, 'OPBEAT', {}),
                    django_settings.DEBUG
                ):
            return response
        data = client.get_data_from_request(request)
        data.update({
            'level': logging.INFO,
            'logger': 'http404',
        })
        result = client.capture(
            'Message',
            param_message={
                'message': 'Page Not Found: %s',
                'params': [request.build_absolute_uri()]
            }, data=data
        )
        request.opbeat = {
            'app_id': data.get('app_id', client.app_id),
            'id': client.get_ident(result),
        }
        return response


def get_name_from_middleware(wrapped, instance):
    name = [type(instance).__name__, wrapped.__name__]
    if type(instance).__module__:
        name = [type(instance).__module__] + name
    return '.'.join(name)


def process_request_wrapper(wrapped, instance, args, kwargs):
    response = wrapped(*args, **kwargs)
    try:
        if response is not None:
            request = args[0]
            request._opbeat_transaction_name = get_name_from_middleware(
                wrapped, instance
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
        if (not hasattr(request, '_opbeat_view_func')
                and response is not original_response):
            request._opbeat_transaction_name = get_name_from_middleware(
                wrapped, instance
            )
    finally:
        return response


class OpbeatAPMMiddleware(MiddlewareMixin):
    _opbeat_instrumented = False
    _instrumenting_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super(OpbeatAPMMiddleware, self).__init__(*args, **kwargs)
        self.client = get_client()

        if not self._opbeat_instrumented:
            with self._instrumenting_lock:
                if not self._opbeat_instrumented:
                    if self.client.instrument_django_middleware:
                        self.instrument_middlewares()

                    OpbeatAPMMiddleware._opbeat_instrumented = True

    def instrument_middlewares(self):
        if getattr(django_settings, 'MIDDLEWARE_CLASSES', None):
            for middleware_path in django_settings.MIDDLEWARE_CLASSES:
                module_path, class_name = middleware_path.rsplit('.', 1)
                try:
                    module = import_module(module_path)
                    middleware_class = getattr(module, class_name)
                    if middleware_class == type(self):
                        # don't instrument ourselves
                        continue
                    if hasattr(middleware_class, 'process_request'):
                        wrapt.wrap_function_wrapper(
                            middleware_class,
                            'process_request',
                            process_request_wrapper,
                        )
                    if hasattr(middleware_class, 'process_response'):
                        wrapt.wrap_function_wrapper(
                            middleware_class,
                            'process_response',
                            process_response_wrapper,
                        )
                except ImportError:
                    client.logger.info(
                        "Can't instrument middleware %s", middleware_path
                    )

    def process_request(self, request):
        if not disabled_due_to_debug(
            getattr(django_settings, 'OPBEAT', {}),
            django_settings.DEBUG
        ):
            self.client.begin_transaction("web.django")

    def process_view(self, request, view_func, view_args, view_kwargs):
        request._opbeat_view_func = view_func

    def process_response(self, request, response):
        try:
            if hasattr(response, 'status_code'):
                # check if _opbeat_transaction_name is set
                if hasattr(request, '_opbeat_transaction_name'):
                    transaction_name = request._opbeat_transaction_name
                elif getattr(request, '_opbeat_view_func', False):
                    transaction_name = get_name_from_func(
                        request._opbeat_view_func
                    )
                else:
                    transaction_name = ''

                status_code = response.status_code
                transaction_name = build_name_with_http_method_prefix(
                    transaction_name,
                    request
                )

                self.client.end_transaction(transaction_name, status_code)
        except Exception:
            self.client.error_logger.error(
                'Exception during timing of request',
                exc_info=True,
            )
        return response


class OpbeatResponseErrorIdMiddleware(MiddlewareMixin):
    """
    Appends the X-Opbeat-ID response header for referencing a message within
    the Opbeat datastore.
    """
    def process_response(self, request, response):
        if not getattr(request, 'opbeat', None):
            return response
        response['X-Opbeat-ID'] = request.opbeat['id']
        return response


class OpbeatLogMiddleware(MiddlewareMixin):
    # Create a thread local variable to store the session in for logging
    thread = threading.local()

    def process_request(self, request):
        self.thread.request = request
