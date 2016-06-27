"""
opbeat.contrib.django.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Acts as an implicit hook for Django installs.

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging
import os
import sys
import warnings

from django.conf import settings as django_settings

import opbeat.instrumentation.control
from opbeat.utils import disabled_due_to_debug, six

logger = logging.getLogger('opbeat.errors.client')


def get_installed_apps():
    """
    Generate a list of modules in settings.INSTALLED_APPS.
    """
    out = set()
    for app in django_settings.INSTALLED_APPS:
        out.add(app)
    return out

_client = (None, None)


class ProxyClient(object):
    """
    A proxy which represents the currenty client at all times.
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
    if six.PY2:
        __cmp__ = lambda x, o: cmp(get_client(), o)
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
    if not six.PY2:
        __long__ = lambda x: long(get_client())
    __float__ = lambda x: float(get_client())
    __str__ = lambda x: str(get_client())
    __unicode__ = lambda x: six.text_type(get_client())
    __oct__ = lambda x: oct(get_client())
    __hex__ = lambda x: hex(get_client())
    __index__ = lambda x: get_client().__index__()
    __coerce__ = lambda x, o: x.__coerce__(x, o)
    __enter__ = lambda x: x.__enter__()
    __exit__ = lambda x, *a, **kw: x.__exit__(*a, **kw)

client = ProxyClient()

default_client_class = 'opbeat.contrib.django.DjangoClient'


def get_client_class(client_path=default_client_class):
    module, class_name = client_path.rsplit('.', 1)
    return getattr(__import__(module, {}, {}, class_name), class_name)


def get_client_config():
    config = getattr(django_settings, 'OPBEAT', {})
    if 'ASYNC' in config:
        warnings.warn(
            'Usage of "ASYNC" configuration is deprecated. Use "ASYNC_MODE"',
            category=DeprecationWarning,
            stacklevel=2,
        )
        config['ASYNC_MODE'] = config['ASYNC']
    return dict(
        servers=config.get('SERVERS', None),
        include_paths=set(
            config.get('INCLUDE_PATHS', [])) | get_installed_apps(),
        exclude_paths=config.get('EXCLUDE_PATHS', None),
        filter_exception_types=config.get('FILTER_EXCEPTION_TYPES', None),
        timeout=config.get('TIMEOUT', None),
        hostname=config.get('HOSTNAME', None),
        auto_log_stacks=config.get('AUTO_LOG_STACKS', None),
        string_max_length=config.get('MAX_LENGTH_STRING', None),
        list_max_length=config.get('MAX_LENGTH_LIST', None),
        organization_id=config.get('ORGANIZATION_ID', None),
        app_id=config.get('APP_ID', None),
        secret_token=config.get('SECRET_TOKEN', None),
        transport_class=config.get('TRANSPORT_CLASS', None),
        processors=config.get('PROCESSORS', None),
        traces_send_freq_secs=config.get('TRACES_SEND_FREQ_SEC', None),
        async_mode=config.get('ASYNC_MODE', None),
        instrument_django_middleware=config.get('INSTRUMENT_DJANGO_MIDDLEWARE'),
        transactions_ignore_patterns=config.get('TRANSACTIONS_IGNORE_PATTERNS', None),
    )


def get_client(client=None):
    """
    Get an Opbeat client.

    :param client:
    :return:
    :rtype: opbeat.base.Client
    """
    global _client

    tmp_client = client is not None
    if not tmp_client:
        config = getattr(django_settings, 'OPBEAT', {})
        client = config.get('CLIENT', default_client_class)

    if _client[0] != client:
        client_class = get_client_class(client)
        instance = client_class(**get_client_config())
        if not tmp_client:
            _client = (client, instance)
        return instance
    return _client[1]


def opbeat_exception_handler(request=None, **kwargs):
    def actually_do_stuff(request=None, **kwargs):
        exc_info = sys.exc_info()
        try:
            if (
                disabled_due_to_debug(
                    getattr(django_settings, 'OPBEAT', {}),
                    django_settings.DEBUG
                )
                or getattr(exc_info[1], 'skip_opbeat', False)
            ):
                return

            get_client().capture('Exception', exc_info=exc_info,
                                 request=request)
        except Exception as exc:
            try:
                logger.exception(u'Unable to process log entry: %s' % (exc,))
            except Exception as exc:
                warnings.warn(u'Unable to process log entry: %s' % (exc,))
        finally:
            try:
                del exc_info
            except Exception as e:
                logger.exception(e)

    return actually_do_stuff(request, **kwargs)


def register_handlers():
    from django.core.signals import got_request_exception

    # Connect to Django's internal signal handler
    got_request_exception.connect(opbeat_exception_handler)

    # If Celery is installed, register a signal handler
    if 'djcelery' in django_settings.INSTALLED_APPS:
        from opbeat.contrib.celery import register_signal

        try:
            register_signal(client)
        except Exception as e:
            logger.exception('Failed installing django-celery hook: %s' % e)

    # Instrument to get traces
    skip_env_var = 'SKIP_INSTRUMENT'
    if skip_env_var in os.environ:
        logger.debug("Skipping instrumentation. %s is set.", skip_env_var)
    else:
        opbeat.instrumentation.control.instrument()


if 'opbeat.contrib.django' in django_settings.INSTALLED_APPS:
    register_handlers()
