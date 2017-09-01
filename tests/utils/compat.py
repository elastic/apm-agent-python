
try:
    from unittest2 import TestCase
    from unittest2 import skipIf
except ImportError:
    from unittest import TestCase
    from unittest import skipIf


def middleware_setting(django_version, middleware_list):
    if django_version < (1, 10):
        return {'MIDDLEWARE_CLASSES': middleware_list}
    else:
        return {'MIDDLEWARE': middleware_list, 'MIDDLEWARE_CLASSES': None}
