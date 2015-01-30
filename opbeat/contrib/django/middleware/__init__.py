"""
opbeat.contrib.django.middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import
import json
import threading
import logging
from datetime import datetime, time

from django.conf import settings
from opbeat.contrib.django.instruments.aggr import instrumentation

from opbeat.contrib.django.instruments.db import enable_instrumentation as db_enable_instrumentation
from opbeat.contrib.django.instruments.cache import enable_instrumentation as cache_enable_instrumentation
from opbeat.contrib.django.instruments.template import enable_instrumentation as template_enable_instrumentation
from opbeat.contrib.django.models import client, get_client


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
        result = client.capture('Message', param_message={'message': 'Page Not Found: %s','params':[request.build_absolute_uri()]}, data=data)
        request.opbeat = {
            'app_id': data.get('app_id', client.app_id),
            'id': client.get_ident(result),
        }
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


class OpbeatMetricsMiddleware(object):
    def __init__(self):
        self.client = get_client()

    def process_request(self, request):
        instrumentation.request_start()
        db_enable_instrumentation()
        cache_enable_instrumentation()
        template_enable_instrumentation()

    def process_view(self, request, view_func, view_args, view_kwargs):
        view_name = "{}.{}".format(view_func.__module__, view_func.__name__)
        instrumentation.set_view(view_name)

    def process_response(self, request, response):
        instrumentation.set_response_code(response.status_code)
        instrumentation.request_end()
        return response
