# -*- coding: utf-8 -*-
import functools

try:
    from unittest2 import TestCase
    from unittest2 import skipIf
except ImportError:
    from unittest import TestCase
    from unittest import skipIf


def noop_decorator(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapped
