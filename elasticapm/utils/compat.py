# -*- coding: utf-8 -*-
import atexit
import functools
import operator
import platform
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

        orig = getattr(uwsgi, "atexit", None)

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

    string_types = (basestring,)  # noqa F821
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

    # for django.utils.datastructures.MultiValueDict
    def iterlists(d, **kw):
        return d.iterlists(**kw)


else:
    import io
    import queue  # noqa F401
    from urllib import parse as urlparse  # noqa F401
    from urllib.error import HTTPError  # noqa F401

    StringIO = io.StringIO
    BytesIO = io.BytesIO

    string_types = (str,)
    integer_types = (int,)
    class_types = (type,)
    text_type = str
    binary_type = bytes

    def b(s):
        return s.encode("latin-1")

    get_function_code = operator.attrgetter("__code__")

    def iterkeys(d, **kwargs):
        return iter(d.keys(**kwargs))

    def iteritems(d, **kwargs):
        return iter(d.items(**kwargs))

    # for django.utils.datastructures.MultiValueDict
    def iterlists(d, **kw):
        return iter(d.lists(**kw))


def get_default_library_patters():
    """
    Returns library paths depending on the used platform.

    :return: a list of glob paths
    """
    python_version = platform.python_version_tuple()
    python_implementation = platform.python_implementation()
    system = platform.system()
    if python_implementation == "PyPy":
        if python_version[0] == "2":
            return ["*/lib-python/%s.%s/*" % python_version[:2], "*/site-packages/*"]
        else:
            return ["*/lib-python/%s/*" % python_version[0], "*/site-packages/*"]
    else:
        if system == "Windows":
            return [r"*\lib\*"]
        return ["*/lib/python%s.%s/*" % python_version[:2], "*/lib64/python%s.%s/*" % python_version[:2]]


def multidict_to_dict(d):
    """
    Turns a werkzeug.MultiDict or django.MultiValueDict into a dict with
    list values
    :param d: a MultiDict or MultiValueDict instance
    :return: a dict instance
    """
    return dict((k, v[0] if len(v) == 1 else v) for k, v in iterlists(d))
