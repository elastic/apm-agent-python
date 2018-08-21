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
from django.conf import settings as django_settings
from django.core.exceptions import DisallowedHost
from django.db import DatabaseError
from django.http import HttpRequest

from elasticapm.base import Client
from elasticapm.conf import constants
from elasticapm.contrib.django.utils import iterate_with_template_sources
from elasticapm.utils import compat, encoding, get_url_dict
from elasticapm.utils.module_import import import_string
from elasticapm.utils.wsgi import get_environ, get_headers

__all__ = ("DjangoClient",)


default_client_class = "elasticapm.contrib.django.DjangoClient"
_client = (None, None)


def get_client(client=None):
    """
    Get an ElasticAPM client.

    :param client:
    :return:
    :rtype: elasticapm.base.Client
    """
    global _client

    tmp_client = client is not None
    if not tmp_client:
        config = getattr(django_settings, "ELASTIC_APM", {})
        client = config.get("CLIENT", default_client_class)

    if _client[0] != client:
        client_class = import_string(client)
        instance = client_class()
        if not tmp_client:
            _client = (client, instance)
        return instance
    return _client[1]


class DjangoClient(Client):
    logger = logging.getLogger("elasticapm.errors.client.django")

    def __init__(self, config=None, **inline):
        if config is None:
            config = getattr(django_settings, "ELASTIC_APM", {})
        if "framework_name" not in inline:
            inline["framework_name"] = "django"
            inline["framework_version"] = django.get_version()
        super(DjangoClient, self).__init__(config, **inline)

    def get_user_info(self, request):
        user_info = {}

        if not hasattr(request, "user"):
            return user_info
        try:
            user = request.user
            if hasattr(user, "is_authenticated"):
                if callable(user.is_authenticated):
                    user_info["is_authenticated"] = user.is_authenticated()
                else:
                    user_info["is_authenticated"] = bool(user.is_authenticated)
            if hasattr(user, "id"):
                user_info["id"] = encoding.keyword_field(user.id)
            if hasattr(user, "get_username"):
                user_info["username"] = encoding.keyword_field(user.get_username())
            elif hasattr(user, "username"):
                user_info["username"] = encoding.keyword_field(user.username)

            if hasattr(user, "email"):
                user_info["email"] = user.email
        except DatabaseError:
            # If the connection is closed or similar, we'll just skip this
            return {}

        return user_info

    def get_data_from_request(self, request, capture_body=False):
        result = {
            "env": dict(get_environ(request.META)),
            "headers": dict(get_headers(request.META)),
            "method": request.method,
            "socket": {"remote_address": request.META.get("REMOTE_ADDR"), "encrypted": request.is_secure()},
            "cookies": dict(request.COOKIES),
        }

        if request.method in constants.HTTP_WITH_BODY:
            content_type = request.META.get("CONTENT_TYPE")
            if content_type == "application/x-www-form-urlencoded":
                data = compat.multidict_to_dict(request.POST)
            elif content_type and content_type.startswith("multipart/form-data"):
                data = compat.multidict_to_dict(request.POST)
                if request.FILES:
                    data["_files"] = {field: file.name for field, file in compat.iteritems(request.FILES)}
            else:
                try:
                    data = request.body
                except Exception:
                    data = "<unavailable>"

            result["body"] = data if (capture_body or not data) else "[REDACTED]"

        if hasattr(request, "get_raw_uri"):
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
                result["url"] = {"full": "DisallowedHost"}
                url = None
        if url:
            result["url"] = get_url_dict(url)
        return result

    def get_data_from_response(self, response):
        result = {"status_code": response.status_code}

        if hasattr(response, "items"):
            result["headers"] = dict(response.items())
        return result

    def capture(self, event_type, request=None, **kwargs):
        if "context" not in kwargs:
            kwargs["context"] = context = {}
        else:
            context = kwargs["context"]

        is_http_request = isinstance(request, HttpRequest)
        if is_http_request:
            context["request"] = self.get_data_from_request(
                request, capture_body=self.config.capture_body in ("all", "errors")
            )
            context["user"] = self.get_user_info(request)

        result = super(DjangoClient, self).capture(event_type, **kwargs)

        if is_http_request:
            # attach the elasticapm object to the request
            request._elasticapm = {"service_name": self.config.service_name, "id": result}

        return result

    def _get_stack_info_for_trace(
        self,
        frames,
        library_frame_context_lines=None,
        in_app_frame_context_lines=None,
        with_locals=True,
        locals_processor_func=None,
    ):
        """If the stacktrace originates within the elasticapm module, it will skip
        frames until some other module comes up."""
        return list(
            iterate_with_template_sources(
                frames,
                with_locals=with_locals,
                library_frame_context_lines=library_frame_context_lines,
                in_app_frame_context_lines=in_app_frame_context_lines,
                include_paths_re=self.include_paths_re,
                exclude_paths_re=self.exclude_paths_re,
                locals_processor_func=locals_processor_func,
            )
        )

    def send(self, url, **kwargs):
        """
        Serializes and signs ``data`` and passes the payload off to ``send_remote``

        If ``server`` was passed into the constructor, this will serialize the data and pipe it to
        the server using ``send_remote()``.
        """
        if self.config.server_url:
            return super(DjangoClient, self).send(url, **kwargs)
        else:
            self.error_logger.error("No server configured, and elasticapm not installed. Cannot send message")
            return None


class ProxyClient(object):
    """
    A proxy which represents the current client at all times.
    """

    # introspection support:
    __members__ = property(lambda x: x.__dir__())

    # Need to pretend to be the wrapped class, for the sake of objects that care
    # about this (especially in equality tests)
    __class__ = property(lambda x: get_client().__class__)

    __dict__ = property(lambda o: get_client().__dict__)

    __repr__ = lambda: repr(get_client())
    __getattr__ = lambda x, o: getattr(get_client(), o)
    __setattr__ = lambda x, o, v: setattr(get_client(), o, v)
    __delattr__ = lambda x, o: delattr(get_client(), o)

    __lt__ = lambda x, o: get_client() < o
    __le__ = lambda x, o: get_client() <= o
    __eq__ = lambda x, o: get_client() == o
    __ne__ = lambda x, o: get_client() != o
    __gt__ = lambda x, o: get_client() > o
    __ge__ = lambda x, o: get_client() >= o
    if compat.PY2:
        __cmp__ = lambda x, o: cmp(get_client(), o)  # noqa F821
    __hash__ = lambda x: hash(get_client())
    # attributes are currently not callable
    # __call__ = lambda x, *a, **kw: get_client()(*a, **kw)
    __nonzero__ = lambda x: bool(get_client())
    __len__ = lambda x: len(get_client())
    __getitem__ = lambda x, i: get_client()[i]
    __iter__ = lambda x: iter(get_client())
    __contains__ = lambda x, i: i in get_client()
    __getslice__ = lambda x, i, j: get_client()[i:j]
    __add__ = lambda x, o: get_client() + o
    __sub__ = lambda x, o: get_client() - o
    __mul__ = lambda x, o: get_client() * o
    __floordiv__ = lambda x, o: get_client() // o
    __mod__ = lambda x, o: get_client() % o
    __divmod__ = lambda x, o: get_client().__divmod__(o)
    __pow__ = lambda x, o: get_client() ** o
    __lshift__ = lambda x, o: get_client() << o
    __rshift__ = lambda x, o: get_client() >> o
    __and__ = lambda x, o: get_client() & o
    __xor__ = lambda x, o: get_client() ^ o
    __or__ = lambda x, o: get_client() | o
    __div__ = lambda x, o: get_client().__div__(o)
    __truediv__ = lambda x, o: get_client().__truediv__(o)
    __neg__ = lambda x: -(get_client())
    __pos__ = lambda x: +(get_client())
    __abs__ = lambda x: abs(get_client())
    __invert__ = lambda x: ~(get_client())
    __complex__ = lambda x: complex(get_client())
    __int__ = lambda x: int(get_client())
    if compat.PY2:
        __long__ = lambda x: long(get_client())  # noqa F821
    __float__ = lambda x: float(get_client())
    __str__ = lambda x: str(get_client())
    __unicode__ = lambda x: compat.text_type(get_client())
    __oct__ = lambda x: oct(get_client())
    __hex__ = lambda x: hex(get_client())
    __index__ = lambda x: get_client().__index__()
    __coerce__ = lambda x, o: x.__coerce__(x, o)
    __enter__ = lambda x: x.__enter__()
    __exit__ = lambda x, *a, **kw: x.__exit__(*a, **kw)


client = ProxyClient()


def _get_installed_apps_paths():
    """
    Generate a list of modules in settings.INSTALLED_APPS.
    """
    out = set()
    for app in django_settings.INSTALLED_APPS:
        out.add(app)
    return out
