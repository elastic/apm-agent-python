"""
opbeat.utils
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2015 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
import os

from opbeat.utils import six


default_ports = {
    "https": 433,
    "http": 80,
    "postgresql": 5432
}


def varmap(func, var, context=None, name=None):
    """
    Executes ``func(key_name, value)`` on all values
    recurisively discovering dict and list scoped
    values.
    """
    if context is None:
        context = {}
    objid = id(var)
    if objid in context:
        return func(name, '<...>')
    context[objid] = 1
    if isinstance(var, dict):
        ret = dict((k, varmap(func, v, context, k)) for k, v in six.iteritems(var))
    elif isinstance(var, (list, tuple)):
        ret = [varmap(func, f, context, name) for f in var]
    else:
        ret = func(name, var)
    del context[objid]
    return ret


def disabled_due_to_debug(opbeat_config, debug):
    """
    Compares module and app configs to determine whether to log to Opbeat
    :param opbeat_config: Dictionary containing module config
    :param debug: Boolean denoting app DEBUG state
    :return: Boolean True if logging is disabled
    """
    return debug and not opbeat_config.get('DEBUG', False)


def get_name_from_func(func):
    # If no view was set we ignore the request
    module = func.__module__

    if hasattr(func, '__name__'):
        view_name = func.__name__
    else:  # Fall back if there's no __name__
        view_name = func.__class__.__name__

    return '{0}.{1}'.format(module, view_name)


def build_name_with_http_method_prefix(name, request):
    if name:
        return request.method + " " + name
    else:
        return name  # 404


def is_master_process():
    # currently only recognizes uwsgi master process
    try:
        import uwsgi
        return os.getpid() == uwsgi.masterpid()
    except ImportError:
        return False
