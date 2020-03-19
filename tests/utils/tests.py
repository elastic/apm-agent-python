#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from functools import partial

import pytest

from elasticapm.conf import constants
from elasticapm.utils import get_name_from_func, get_url_dict, sanitize_url, starmatch_to_regex, url_to_destination
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


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "http://example.com",
            {"protocol": "http:", "hostname": "example.com", "pathname": "", "full": "http://example.com"},
        ),
        (
            "http://example.com:443",
            {
                "protocol": "http:",
                "hostname": "example.com",
                "port": "443",
                "pathname": "",
                "full": "http://example.com:443",
            },
        ),
        (
            "http://example.com:443/a/b/c",
            {
                "protocol": "http:",
                "hostname": "example.com",
                "port": "443",
                "pathname": "/a/b/c",
                "full": "http://example.com:443/a/b/c",
            },
        ),
        (
            "https://example.com:443/",
            {
                "protocol": "https:",
                "hostname": "example.com",
                "port": "443",
                "pathname": "/",
                "full": "https://example.com:443/",
            },
        ),
        (
            "https://example.com:443/a/b/c?de",
            {
                "protocol": "https:",
                "hostname": "example.com",
                "port": "443",
                "pathname": "/a/b/c",
                "search": "?de",
                "full": "https://example.com:443/a/b/c?de",
            },
        ),
        (
            "https://[::ffff:a9fe:a9fe]/a/b/c?de",
            {
                "protocol": "https:",
                "hostname": "::ffff:a9fe:a9fe",
                "pathname": "/a/b/c",
                "search": "?de",
                "full": "https://[::ffff:a9fe:a9fe]/a/b/c?de",
            },
        ),
        (
            "http://[::ffff:a9fe:a9fe]:80/a/b/c?de",
            {
                "protocol": "http:",
                "hostname": "::ffff:a9fe:a9fe",
                "port": "80",
                "pathname": "/a/b/c",
                "search": "?de",
                "full": "http://[::ffff:a9fe:a9fe]:80/a/b/c?de",
            },
        ),
    ],
)
def test_get_url_dict(url, expected):
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


@pytest.mark.parametrize(
    "pattern,input,match",
    [
        ("a*c", "abc", True),
        ("a*c", "abcd", False),
        ("a*c*", "abcd", True),
        ("a.c", "abc", False),
        ("a?c", "abc", False),
    ],
)
def test_starmatch_to_regex(pattern, input, match):
    re_pattern = starmatch_to_regex(pattern)
    assert bool(re_pattern.match(input)) is match, re_pattern.pattern


def test_url_sanitization():
    sanitized = sanitize_url("http://user:pass@localhost:123/foo?bar=baz#bazzinga")
    assert sanitized == "http://user:%s@localhost:123/foo?bar=baz#bazzinga" % constants.MASK


def test_url_sanitization_urlencoded_password():
    sanitized = sanitize_url("http://user:%F0%9F%9A%B4@localhost:123/foo?bar=baz#bazzinga")
    assert sanitized == "http://user:%s@localhost:123/foo?bar=baz#bazzinga" % constants.MASK


@pytest.mark.parametrize(
    "url,name,resource",
    [
        ("http://user:pass@testing.local:1234/path?query", "http://testing.local:1234", "testing.local:1234"),
        ("https://www.elastic.co:443/products/apm", "https://www.elastic.co", "www.elastic.co:443"),
        ("http://[::1]/", "http://[::1]", "[::1]:80"),
    ],
)
def test_url_to_destination(url, name, resource):
    destination = url_to_destination(url)
    assert destination["service"]["name"] == name
    assert destination["service"]["resource"] == resource
