# -*- coding: utf-8 -*-
import atexit
import functools
import operator
import sys
import types


def noop_decorator(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapped


def atexit_register(func):
    """
    Uses either uwsgi's atexit mechanism, or atexit from the stdlib.

    When running under uwsgi, using their atexit handler is more reliable,
    especially when using gevent
    :param func: the function to call at exit
    """
    try:
        import uwsgi
        orig = getattr(uwsgi, 'atexit', None)

        def uwsgi_atexit():
            if callable(orig):
                orig()
            func()

        uwsgi.atexit = uwsgi_atexit
    except ImportError:
        atexit.register(func)


# Compatibility layer for Python2/Python3, partly inspired by /modified from six, https://github.com/benjaminp/six
# Remainder of this file: Copyright Benjamin Peterson, MIT License https://github.com/benjaminp/six/blob/master/LICENSE

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3


if PY2:
    import StringIO
    import Queue as queue  # noqa F401
    import urlparse  # noqa F401
    from urllib2 import HTTPError  # noqa F401

    StringIO = BytesIO = StringIO.StringIO

    string_types = basestring,  # noqa F821
    integer_types = (int, long)  # noqa F821
    class_types = (type, types.ClassType)
    text_type = unicode  # noqa F821
    binary_type = str

    def b(s):
        return s

    get_function_code = operator.attrgetter("func_code")

    def iterkeys(d, **kwargs):
        return d.iterkeys(**kwargs)

    def iteritems(d, **kwargs):
        return d.iteritems(**kwargs)
else:
    import io
    import queue  # noqa F401
    from urllib import parse as urlparse  # noqa F401
    from urllib.error import HTTPError  # noqa F401

    StringIO = io.StringIO
    BytesIO = io.BytesIO

    string_types = str,
    integer_types = int,
    class_types = type,
    text_type = str
    binary_type = bytes

    def b(s):
        return s.encode("latin-1")

    get_function_code = operator.attrgetter("__code__")

    def iterkeys(d, **kwargs):
        return iter(d.keys(**kwargs))

    def iteritems(d, **kwargs):
        return iter(d.items(**kwargs))
