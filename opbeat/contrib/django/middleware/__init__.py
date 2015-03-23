"""
opbeat.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import
import time
import logging
import threading
import wrapt

from django.http.request import HttpRequest

from django.conf import settings as django_settings


try:
    from importlib import import_module
except ImportError:
    from django.utils.importlib import import_module

from opbeat.contrib.django.models import client, get_client
from opbeat.utils import disabled_due_to_debug


def _is_ignorable_404(uri):
    """
    Returns True if the given request *shouldn't* notify the site managers.
    """
    urls = getattr(django_settings, 'IGNORABLE_404_URLS', ())
    return any(pattern.search(uri) for pattern in urls)


class Opbeat404CatchMiddleware(object):
    def process_response(self, request, response):
        if response.status_code != 404 or _is_ignorable_404(
                request.get_full_path()
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


def process_request_wrapper(wrapped, instance, args, kwargs):
    response = wrapped(*args, **kwargs)
    try:
        if response is not None:
            request = None
            if args and isinstance(args[0], HttpRequest):
                request = args[0]
            elif 'request' in kwargs and isinstance(kwargs['request'], HttpRequest):
                request = kwargs['request']
            if request is not None:
                name = [type(instance).__name__, wrapped.__name__]
                if type(instance).__module__:
                    name.insert(0, type(instance).__module__)
                request._opbeat_transaction_name = '.'.join(name)
    finally:
        return response


class OpbeatAPMMiddleware(object):
    def __init__(self):
        self.client = get_client()
        if self.client.wrap_django_middleware:
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
                            process_request_wrapper
                        )
                except ImportError:
                    client.logger.info(
                        "Can't instrument middleware %s", middleware_path
                    )

    def _get_name_from_view_func(self, view_func):
        # If no view was set we ignore the request
        module = view_func.__module__

        if hasattr(view_func, '__name__'):
            view_name = view_func.__name__
        else:  # Fall back if there's no __name__
            view_name = view_func.__class__.__name__

        return '{0}.{1}'.format(module, view_name)

    def process_request(self, request):
        if not disabled_due_to_debug(
            getattr(django_settings, 'OPBEAT', {}),
            django_settings.DEBUG
        ):
            request._opbeat_request_start = time.time()

    def process_view(self, request, view_func, view_args, view_kwargs):
        request._opbeat_view_func = view_func

    def process_response(self, request, response):
        try:
            if (hasattr(request, '_opbeat_request_start')
                    and hasattr(response, 'status_code')):
                elapsed = (time.time() - request._opbeat_request_start) * 1000

                if getattr(request, '_opbeat_view_func', False):
                    view_func = self._get_name_from_view_func(
                        request._opbeat_view_func)
                else:
                    view_func = getattr(
                        request,
                        '_opbeat_transaction_name',
                        ''
                    )
                status_code = response.status_code
                self.client.captureRequest(elapsed, status_code, view_func)
        except Exception:
            self.client.error_logger.error(
                'Exception during timing of request',
                exc_info=True,
            )
        return response


class OpbeatResponseErrorIdMiddleware(object):
    """
    Appends the X-Opbeat-ID response header for referencing a message within
    the Opbeat datastore.
    """
    def process_response(self, request, response):
        if not getattr(request, 'opbeat', None):
            return response
        response['X-Opbeat-ID'] = request.opbeat['id']
        return response


class OpbeatLogMiddleware(object):
    # Create a thread local variable to store the session in for logging
    thread = threading.local()

    def process_request(self, request):
        self.thread.request = request
