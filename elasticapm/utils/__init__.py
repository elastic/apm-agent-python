"""
elasticapm.utils
~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2017 Elasticsearch

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
import os

from elasticapm.utils import compat

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


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
        ret = dict((k, varmap(func, v, context, k)) for k, v in compat.iteritems(var))
    elif isinstance(var, (list, tuple)):
        ret = [varmap(func, f, context, name) for f in var]
    else:
        ret = func(name, var)
    del context[objid]
    return ret


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


def get_url_dict(url):
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    if ':' in netloc:
        hostname, port = netloc.split(':')
    else:
        hostname, port = (netloc, None)
    return {
        'raw': url,
        'protocol': scheme + ':',
        'hostname': hostname,
        'port': port,
        'pathname': path,
        'search': query,
        'hash': fragment,
    }
