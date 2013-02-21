"""
opbeat.contrib.django.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

from django.http import HttpRequest
from django.template import TemplateSyntaxError
from django.template.loader import LoaderOrigin

from opbeat.base import Client
from opbeat.contrib.django.utils import get_data_from_template
from opbeat.utils.wsgi import get_headers, get_environ

__all__ = ('DjangoClient',)


class DjangoClient(Client):
    logger = logging.getLogger('opbeat.errors.client.django')

    def get_user_info(self, request):
        if request.user.is_authenticated():
            user_info = {
                'is_authenticated': True,
                'id': request.user.pk,
                'username': request.user.username,
                'email': request.user.email,
            }
        else:
            user_info = {
                'is_authenticated': False,
            }
        return user_info

    def get_data_from_request(self, request):
        from django.contrib.auth.models import User, AnonymousUser

        if request.method != 'GET':
            try:
                data = request.raw_post_data and request.raw_post_data or request.POST
            except Exception:
                # assume we had a partial read:
                data = '<unavailable>'
        else:
            data = None

        environ = request.META

        result = {
            'http': {
                'method': request.method,
                'url': request.build_absolute_uri(),
                'query_string': request.META.get('QUERY_STRING'),
                'data': data,
                'cookies': dict(request.COOKIES),
                'headers': dict(get_headers(environ)),
                'env': dict(get_environ(environ)),
            }
        }

        if hasattr(request, 'user') and isinstance(request.user, (User, AnonymousUser)):
            result['user'] = self.get_user_info(request)

        return result

    def capture(self, event_type, request=None, **kwargs):
        if 'data' not in kwargs:
            kwargs['data'] = data = {}
        else:
            data = kwargs['data']

        is_http_request = isinstance(request, HttpRequest)
        if is_http_request:
            data.update(self.get_data_from_request(request))

        if kwargs.get('exc_info'):
            exc_value = kwargs['exc_info'][1]
            # As of r16833 (Django) all exceptions may contain a ``django_template_source`` attribute (rather than the
            # legacy ``TemplateSyntaxError.source`` check) which describes template information.
            if hasattr(exc_value, 'django_template_source') or ((isinstance(exc_value, TemplateSyntaxError) and
               isinstance(getattr(exc_value, 'source', None), (tuple, list)) and isinstance(exc_value.source[0], LoaderOrigin))):
                source = getattr(exc_value, 'django_template_source', getattr(exc_value, 'source', None))
                if source is None:
                    self.logger.info('Unable to get template source from exception')
                data.update(get_data_from_template(source))

        result = super(DjangoClient, self).capture(event_type, **kwargs)

        if is_http_request:
            # attach the opbeat object to the request
            request.opbeat = {
                'app_id': data.get('app_id', self.app_id),
                'id': self.get_ident(result),
            }

        return result

    def send(self, **kwargs):
        """
        Serializes and signs ``data`` and passes the payload off to ``send_remote``

        If ``servers`` was passed into the constructor, this will serialize the data and pipe it to
        each server using ``send_remote()``.
        """
        if self.servers:
            return super(DjangoClient, self).send(**kwargs)
        else:
            self.error_logger.error('No servers configured, and opbeat not installed. Cannot send message')
            return None
