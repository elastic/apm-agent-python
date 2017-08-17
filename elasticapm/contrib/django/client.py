"""
elasticapm.contrib.django.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

import django
from django.core.exceptions import DisallowedHost
from django.db import DatabaseError
from django.http import HttpRequest
from django.template import TemplateSyntaxError

from elasticapm.base import Client
from elasticapm.conf import defaults
from elasticapm.contrib.django.utils import (get_data_from_template_debug,
                                             get_data_from_template_source,
                                             iterate_with_template_sources)
from elasticapm.utils import get_url_dict
from elasticapm.utils.wsgi import get_environ, get_headers

try:
    from django.template.loader import LoaderOrigin  # Django < 1.9
except ImportError:
    from django.template.base import Origin as LoaderOrigin  # Django >= 1.9


try:
    # Attempt to use the Django 1.7+ apps sub-framework.
    from django.apps import apps

    is_app_installed = apps.is_installed
except ImportError:
    from django.conf import settings

    # Use the legacy method of simple checking the configuration.
    def is_app_installed(app_name):
        return app_name in settings.INSTALLED_APPS


__all__ = ('DjangoClient',)


class DjangoClient(Client):
    logger = logging.getLogger('elasticapm.errors.client.django')

    def __init__(self, **kwargs):
        instrument_django_middleware = kwargs.pop(
            'instrument_django_middleware',
            None
        )
        if instrument_django_middleware is not None:
            self.instrument_django_middleware = instrument_django_middleware
        else:
            self.instrument_django_middleware = defaults.INSTRUMENT_DJANGO_MIDDLEWARE
        self._framework = 'django'
        self._framework_version = django.get_version()
        super(DjangoClient, self).__init__(**kwargs)

    def get_user_info(self, request):
        user_info = {}

        if not hasattr(request, 'user'):
            return user_info
        try:
            user = request.user
            if hasattr(user, 'is_authenticated'):
                if callable(user.is_authenticated):
                    user_info['is_authenticated'] = user.is_authenticated()
                else:
                    user_info['is_authenticated'] = bool(user.is_authenticated)
            if hasattr(user, 'id'):
                user_info['id'] = user.id
            if hasattr(user, 'get_username'):
                user_info['username'] = user.get_username()
            elif hasattr(user, 'username'):
                user_info['username'] = user.username

            if hasattr(user, 'email'):
                user_info['email'] = user.email
        except DatabaseError:
            # If the connection is closed or similar, we'll just skip this
            return {}

        return user_info

    def get_data_from_request(self, request):
        if request.method != 'GET':
            try:
                if hasattr(request, 'body'):
                    # Django 1.4+
                    raw_data = request.body
                else:
                    raw_data = request.raw_post_data
                data = raw_data if raw_data else request.POST
            except Exception:
                # assume we had a partial read:
                data = '<unavailable>'
        else:
            data = None

        environ = request.META

        result = {
            'body': data,
            'env': dict(get_environ(environ)),
            'headers': dict(get_headers(environ)),
            'method': request.method,
            'socket': {
                'remote_address': request.META.get('REMOTE_ADDR'),
                'encrypted': request.is_secure()
            },
            'cookies': dict(request.COOKIES),
        }

        if hasattr(request, 'get_raw_uri'):
            # added in Django 1.9
            url = request.get_raw_uri()
        else:
            try:
                # Requires host to be in ALLOWED_HOSTS, might throw a
                # DisallowedHost exception
                url = request.build_absolute_uri()
            except DisallowedHost:
                # We can't figure out the real URL, so we have to set it to
                # DisallowedHost
                result['url'] = {'raw': 'DisallowedHost'}
                url = None
        if url:
            result['url'] = get_url_dict(url)
        return result

    def capture(self, event_type, request=None, **kwargs):
        if 'data' not in kwargs:
            kwargs['data'] = data = {}
        else:
            data = kwargs['data']

        if 'context' not in data:
            data['context'] = context = {}
        else:
            context = data['context']

        is_http_request = isinstance(request, HttpRequest)
        if is_http_request:
            context['request'] = self.get_data_from_request(request)
            context['user'] = self.get_user_info(request)

        if kwargs.get('exc_info'):
            exc_value = kwargs['exc_info'][1]
            # As of r16833 (Django) all exceptions may contain a ``django_template_source`` attribute (rather than the
            # legacy ``TemplateSyntaxError.source`` check) which describes template information.
            if hasattr(exc_value, 'django_template_source') or ((isinstance(exc_value, TemplateSyntaxError) and
               isinstance(getattr(exc_value, 'source', None), (tuple, list)) and isinstance(exc_value.source[0], LoaderOrigin))):
                source = getattr(exc_value, 'django_template_source', getattr(exc_value, 'source', None))
                if source is None:
                    self.logger.info('Unable to get template source from exception')
                data.update(get_data_from_template_source(source))
            elif hasattr(exc_value, 'template_debug'):  # Django 1.9+
                data.update(get_data_from_template_debug(exc_value.template_debug))

        result = super(DjangoClient, self).capture(event_type, **kwargs)

        if is_http_request:
            # attach the elasticapm object to the request
            request._elasticapm = {
                'app_name': data.get('app_name', self.app_name),
                'id': self.get_ident(result),
            }

        return result

    def get_stack_info_for_trace(self, frames, extended=True):
        """If the stacktrace originates within the elasticapm module, it will skip
        frames until some other module comes up."""
        frames = list(iterate_with_template_sources(frames, extended))
        i = 0
        while len(frames) > i:
            if 'module' in frames[i] and not (
                    frames[i]['module'].startswith('elasticapm.') or
                    frames[i]['module'] == 'contextlib'
            ):
                return frames[i:]
            i += 1
        return frames

    def send(self, **kwargs):
        """
        Serializes and signs ``data`` and passes the payload off to ``send_remote``

        If ``servers`` was passed into the constructor, this will serialize the data and pipe it to
        each server using ``send_remote()``.
        """
        if self.servers:
            return super(DjangoClient, self).send(**kwargs)
        else:
            self.error_logger.error('No servers configured, and elasticapm not installed. Cannot send message')
            return None
