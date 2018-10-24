from functools import partial

import pytest

from elasticapm.utils import get_name_from_func, get_url_dict
from elasticapm.utils.deprecation import deprecated

try:
    from functools import partialmethod
except ImportError:
    # Python 2
    partialmethod = None


@deprecated("alternative")
def deprecated_function():
    pass


def test_deprecation():
    deprecated_function()


def test_get_url_dict():
    data = {
        "http://example.com": {
            "protocol": "http:",
            "hostname": "example.com",
            "pathname": "",
            "full": "http://example.com",
        },
        "http://example.com:443": {
            "protocol": "http:",
            "hostname": "example.com",
            "port": "443",
            "pathname": "",
            "full": "http://example.com:443",
        },
        "http://example.com:443/a/b/c": {
            "protocol": "http:",
            "hostname": "example.com",
            "port": "443",
            "pathname": "/a/b/c",
            "full": "http://example.com:443/a/b/c",
        },
        "https://example.com:443/": {
            "protocol": "https:",
            "hostname": "example.com",
            "port": "443",
            "pathname": "/",
            "full": "https://example.com:443/",
        },
        "https://example.com:443/a/b/c?de": {
            "protocol": "https:",
            "hostname": "example.com",
            "port": "443",
            "pathname": "/a/b/c",
            "search": "?de",
            "full": "https://example.com:443/a/b/c?de",
        },
    }
    for url, expected in data.items():
        assert get_url_dict(url) == expected


def test_get_name_from_func():
    def x():
        pass

    assert "tests.utils.tests.x" == get_name_from_func(x)


def test_get_name_from_func_class():
    class X(object):
        def x(self):
            pass

    assert "tests.utils.tests.x" == get_name_from_func(X.x)
    assert "tests.utils.tests.x" == get_name_from_func(X().x)


def test_get_name_from_func_partial():
    def x(x):
        pass

    p = partial(x, "x")
    assert "partial(tests.utils.tests.x)" == get_name_from_func(p)


@pytest.mark.skipif(partialmethod is None, reason="partialmethod not available on Python 2")
def test_get_name_from_func_partialmethod_unbound():
    class X(object):
        def x(self, x):
            pass

        p = partialmethod(x, "x")

    assert "partial(tests.utils.tests.x)" == get_name_from_func(X.p)


@pytest.mark.skipif(partialmethod is None, reason="partialmethod not available on Python 2")
def test_get_name_from_func_partialmethod_bound():
    class X(object):
        def x(self, x):
            pass

        p = partialmethod(x, "x")

    assert "partial(tests.utils.tests.x)" == get_name_from_func(X().p)


def test_get_name_from_func_lambda():
    assert "tests.utils.tests.<lambda>" == get_name_from_func(lambda x: "x")
