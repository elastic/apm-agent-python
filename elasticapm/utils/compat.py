# -*- coding: utf-8 -*-
import atexit
import functools

try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse

try:
    from urllib2 import HTTPError
except ImportError:
    from urllib.error import HTTPError


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
