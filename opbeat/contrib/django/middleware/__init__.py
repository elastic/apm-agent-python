"""
opbeat.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import
from collections import defaultdict
from datetime import datetime
from django.conf import settings
from opbeat.contrib.django.models import client, get_client
from opbeat.utils.metrics import Aggregator
import threading
import logging

def _is_ignorable_404(uri):
    """
    Returns True if the given request *shouldn't* notify the site managers.
    """
    urls = getattr(settings, 'IGNORABLE_404_URLS', ())
    return any(pattern.search(uri) for pattern in urls)


class Opbeat404CatchMiddleware(object):
    def process_response(self, request, response):
        if response.status_code != 404 or _is_ignorable_404(request.get_full_path()):
            return response
        data = client.get_data_from_request(request)
        data.update({
            'level': logging.INFO,
            'logger': 'http404',
        })
        result = client.capture('Message', param_message={'message':'Page Not Found: %s','params':[request.build_absolute_uri()]}, data=data)
        request.opbeat = {
            'app_id': data.get('app_id', client.app_id),
            'id': client.get_ident(result),
        }
        return response


class OpbeatMetricsMiddleware(object):
    # Create a threadlocal variable to store the session in for logging
    thread_local = threading.local()

    def __init__(self):
        self.client = get_client()

    def process_request(self, request):
        self.thread_local.request_start = datetime.now()

    def process_view(self, request, view_func, view_args, view_kwargs):
        self.thread_local.view_func = view_func

    def process_response(self, request, response):
        try:
            if (hasattr(self.thread_local, "request_start")
                    and hasattr(response, "status_code")):
                elapsed = (datetime.now() - self.thread_local.request_start)\
                    .total_seconds()*1000

                if hasattr(self.thread_local, "view_func"):
                    view_func = "{}.{}".format(
                        self.thread_local.view_func.__module__,
                        self.thread_local.view_func.__name__)
                else:
                    view_func = None

                status_code = response.status_code
                self.client.captureRequest(elapsed, status_code, view_func)
        except Exception:
            self.client.error_logger.error(
                'Exception during metrics tracking',
                exc_info=True,
            )
        finally:
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
    # Create a threadlocal variable to store the session in for logging
    thread = threading.local()

    def process_request(self, request):
        self.thread.request = request
