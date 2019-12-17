# -*- coding: utf-8 -*-

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

import pytest  # isort:skip

django = pytest.importorskip("django")  # isort:skip


import json
import logging
import os
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.core.handlers.wsgi import WSGIRequest
from django.core.management import call_command
from django.core.signals import got_request_exception
from django.db import DatabaseError
from django.http import QueryDict
from django.http.cookie import SimpleCookie
from django.test.client import Client as _TestClient
from django.test.client import ClientHandler as _TestClientHandler
from django.test.utils import override_settings

import mock

from elasticapm.base import Client
from elasticapm.conf import constants
from elasticapm.conf.constants import ERROR, SPAN, TRANSACTION
from elasticapm.contrib.django.apps import ElasticAPMConfig
from elasticapm.contrib.django.client import client, get_client
from elasticapm.contrib.django.handlers import LoggingHandler
from elasticapm.contrib.django.middleware.wsgi import ElasticAPM
from elasticapm.utils import compat
from elasticapm.utils.disttracing import TraceParent
from tests.contrib.django.conftest import BASE_TEMPLATE_DIR
from tests.contrib.django.testapp.views import IgnoredException, MyException
from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse


try:
    from celery.tests.utils import with_eager_tasks

    has_with_eager_tasks = True
except ImportError:
    from elasticapm.utils.compat import noop_decorator as with_eager_tasks

    has_with_eager_tasks = False

pytestmark = pytest.mark.django


class MockClientHandler(_TestClientHandler):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return super(MockClientHandler, self).__call__(environ)


class MockMiddleware(ElasticAPM):
    def __call__(self, environ, start_response=[]):
        # this pretends doesnt require start_response
        return list(super(MockMiddleware, self).__call__(environ, start_response))


def test_proxy_responds_as_client():
    assert get_client() == client


def test_basic(django_elasticapm_client):
    config = {"APP_ID": "key", "ORGANIZATION_ID": "org", "SECRET_TOKEN": "99"}
    with override_settings(ELASTIC_APM=config):
        django_elasticapm_client.capture("Message", message="foo")
        assert len(django_elasticapm_client.events[ERROR]) == 1


def test_basic_django(django_elasticapm_client):
    django_elasticapm_client.capture("Message", message="foo")
    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    log = event["log"]
    assert "message" in log

    assert log["message"] == "foo"
    assert log["level"] == "error"
    assert log["param_message"] == "foo"


def test_signal_integration(django_elasticapm_client):
    try:
        int("hello")
    except ValueError:
        got_request_exception.send(sender=None, request=None)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "exception" in event
    exc = event["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == u"ValueError: invalid literal for int() with base 10: 'hello'"
    assert exc["handled"] is False
    assert event["culprit"] == "tests.contrib.django.django_tests.test_signal_integration"


def test_view_exception(django_elasticapm_client, client):
    with pytest.raises(Exception):
        client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "exception" in event
    exc = event["exception"]
    assert exc["type"] == "MyException"
    assert exc["message"] == "MyException: view exception"
    assert exc["handled"] is False
    assert event["culprit"] == "tests.contrib.django.testapp.views.raise_exc"


def test_view_exception_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = False
    with override_settings(DEBUG=True):
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))
    assert len(django_elasticapm_client.events) == 0


def test_view_exception_elasticapm_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = True
    with override_settings(DEBUG=True):
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))
    assert len(django_elasticapm_client.events[ERROR]) == 1


@pytest.mark.django_db
def test_user_info(django_elasticapm_client, client):
    user = User(username="admin", email="admin@example.com")
    user.set_password("admin")
    user.save()

    with pytest.raises(Exception):
        client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "user" in event["context"]
    user_info = event["context"]["user"]
    assert "is_authenticated" in user_info
    assert not user_info["is_authenticated"]
    assert user_info["username"] == ""
    assert "email" not in user_info

    assert client.login(username="admin", password="admin")

    with pytest.raises(Exception):
        client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 2
    event = django_elasticapm_client.events[ERROR][1]
    assert "user" in event["context"]
    user_info = event["context"]["user"]
    assert "is_authenticated" in user_info
    assert user_info["is_authenticated"]
    assert "username" in user_info
    assert user_info["username"] == "admin"
    assert "email" in user_info
    assert user_info["email"] == "admin@example.com"


@pytest.mark.django_db
def test_user_info_raises_database_error(django_elasticapm_client, client):
    user = User(username="admin", email="admin@example.com")
    user.set_password("admin")
    user.save()

    assert client.login(username="admin", password="admin")

    with mock.patch("django.contrib.auth.models.User.is_authenticated") as is_authenticated:
        is_authenticated.side_effect = DatabaseError("Test Exception")
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "user" in event["context"]
    user_info = event["context"]["user"]
    assert user_info == {}


@pytest.mark.django_db
def test_user_info_with_custom_user(django_elasticapm_client, client):
    with override_settings(AUTH_USER_MODEL="testapp.MyUser"):
        from django.contrib.auth import get_user_model

        MyUser = get_user_model()
        user = MyUser(my_username="admin")
        user.set_password("admin")
        user.save()
        assert client.login(username="admin", password="admin")
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]
        assert "user" in event["context"]
        user_info = event["context"]["user"]
        assert "is_authenticated" in user_info
        assert user_info["is_authenticated"]
        assert "username" in user_info
        assert user_info["username"] == "admin"
        assert "email" not in user_info


@pytest.mark.django_db
def test_user_info_with_custom_user_non_string_username(django_elasticapm_client, client):
    with override_settings(AUTH_USER_MODEL="testapp.MyIntUser"):
        from django.contrib.auth import get_user_model

        MyIntUser = get_user_model()
        user = MyIntUser(my_username=1)
        user.set_password("admin")
        user.save()
        assert client.login(username=1, password="admin")
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]
        assert "user" in event["context"]
        user_info = event["context"]["user"]
        assert "username" in user_info
        assert isinstance(user_info["username"], compat.text_type)
        assert user_info["username"] == "1"


@pytest.mark.skipif(django.VERSION > (1, 9), reason="MIDDLEWARE_CLASSES removed in Django 2.0")
def test_user_info_with_non_django_auth(django_elasticapm_client, client):
    with override_settings(
        INSTALLED_APPS=[app for app in settings.INSTALLED_APPS if app != "django.contrib.auth"]
    ) and override_settings(
        MIDDLEWARE_CLASSES=[
            m for m in settings.MIDDLEWARE_CLASSES if m != "django.contrib.auth.middleware.AuthenticationMiddleware"
        ]
    ):
        with pytest.raises(Exception):
            resp = client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["user"] == {}


@pytest.mark.skipif(django.VERSION < (1, 10), reason="MIDDLEWARE new in Django 1.10")
def test_user_info_with_non_django_auth_django_2(django_elasticapm_client, client):
    with override_settings(
        INSTALLED_APPS=[app for app in settings.INSTALLED_APPS if app != "django.contrib.auth"]
    ) and override_settings(
        MIDDLEWARE_CLASSES=None,
        MIDDLEWARE=[m for m in settings.MIDDLEWARE if m != "django.contrib.auth.middleware.AuthenticationMiddleware"],
    ):
        with pytest.raises(Exception):
            resp = client.get(reverse("elasticapm-raise-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["user"] == {}


@pytest.mark.skipif(django.VERSION > (1, 9), reason="MIDDLEWARE_CLASSES removed in Django 2.0")
def test_user_info_without_auth_middleware(django_elasticapm_client, client):
    with override_settings(
        MIDDLEWARE_CLASSES=[
            m for m in settings.MIDDLEWARE_CLASSES if m != "django.contrib.auth.middleware.AuthenticationMiddleware"
        ]
    ):
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))
    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["user"] == {}


@pytest.mark.skipif(django.VERSION < (1, 10), reason="MIDDLEWARE new in Django 1.10")
def test_user_info_without_auth_middleware_django_2(django_elasticapm_client, client):
    with override_settings(
        MIDDLEWARE_CLASSES=None,
        MIDDLEWARE=[m for m in settings.MIDDLEWARE if m != "django.contrib.auth.middleware.AuthenticationMiddleware"],
    ):
        with pytest.raises(Exception):
            client.get(reverse("elasticapm-raise-exc"))
    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["user"] == {}


def test_request_middleware_exception(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["tests.contrib.django.testapp.middleware.BrokenRequestMiddleware"])
    ):
        with pytest.raises(ImportError):
            client.get(reverse("elasticapm-raise-exc"))

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]

        assert "exception" in event
        exc = event["exception"]
        assert exc["type"] == "ImportError"
        assert exc["message"] == "ImportError: request"
        assert exc["handled"] is False
        assert event["culprit"] == "tests.contrib.django.testapp.middleware.process_request"


def test_response_middlware_exception(django_elasticapm_client, client):
    if django.VERSION[:2] < (1, 3):
        return
    with override_settings(
        **middleware_setting(django.VERSION, ["tests.contrib.django.testapp.middleware.BrokenResponseMiddleware"])
    ):
        with pytest.raises(ImportError):
            client.get(reverse("elasticapm-no-error"))

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]

        assert "exception" in event
        exc = event["exception"]
        assert exc["type"] == "ImportError"
        assert exc["message"] == "ImportError: response"
        assert exc["handled"] is False
        assert event["culprit"] == "tests.contrib.django.testapp.middleware.process_response"


def test_broken_500_handler_with_middleware(django_elasticapm_client, client):
    with override_settings(BREAK_THAT_500=True):
        client.handler = MockMiddleware(MockClientHandler())

        with override_settings(**middleware_setting(django.VERSION, [])):
            with pytest.raises(Exception):
                client.get(reverse("elasticapm-raise-exc"))

        assert len(django_elasticapm_client.events[ERROR]) == 2

        event = django_elasticapm_client.events[ERROR][0]

        assert "exception" in event
        exc = event["exception"]
        assert exc["type"] == "MyException"
        assert exc["message"] == "MyException: view exception"
        assert event["culprit"] == "tests.contrib.django.testapp.views.raise_exc"

        event = django_elasticapm_client.events[ERROR][1]

        assert "exception" in event
        exc = event["exception"]
        assert exc["type"] == "ValueError"
        assert exc["message"] == "ValueError: handler500"
        assert exc["handled"] is False
        assert event["culprit"] == "tests.contrib.django.testapp.urls.handler500"


def test_view_middleware_exception(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["tests.contrib.django.testapp.middleware.BrokenViewMiddleware"])
    ):
        with pytest.raises(ImportError):
            client.get(reverse("elasticapm-raise-exc"))

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]

        assert "exception" in event
        exc = event["exception"]
        assert exc["type"] == "ImportError"
        assert exc["message"] == "ImportError: view"
        assert exc["handled"] is False
        assert event["culprit"] == "tests.contrib.django.testapp.middleware.process_view"


def test_exclude_modules_view(django_elasticapm_client, client):
    django_elasticapm_client.config.exclude_paths = ["tests.views.decorated_raise_exc"]
    with pytest.raises(Exception):
        client.get(reverse("elasticapm-raise-exc-decor"))

    assert len(django_elasticapm_client.events[ERROR]) == 1, django_elasticapm_client.events
    event = django_elasticapm_client.events[ERROR][0]

    assert event["culprit"] == "tests.contrib.django.testapp.views.raise_exc"


def test_include_modules(django_elasticapm_client, client):
    django_elasticapm_client.config.include_paths = ["django.shortcuts.get_object_or_404"]

    with pytest.raises(Exception):
        client.get(reverse("elasticapm-django-exc"))

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert event["culprit"] == "django.shortcuts.get_object_or_404"


def test_ignored_exception_is_ignored(django_elasticapm_client, client):
    with pytest.raises(IgnoredException):
        client.get(reverse("elasticapm-ignored-exception"))
    assert len(django_elasticapm_client.events[ERROR]) == 0


@pytest.mark.skipif(compat.PY3, reason="see Python bug #10805")
def test_record_none_exc_info(django_elasticapm_client):
    # sys.exc_info can return (None, None, None) if no exception is being
    # handled anywhere on the stack. See:
    #  http://docs.python.org/library/sys.html#sys.exc_info
    record = logging.LogRecord(
        "foo", logging.INFO, pathname=None, lineno=None, msg="test", args=(), exc_info=(None, None, None)
    )
    handler = LoggingHandler()
    handler.emit(record)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert event["log"]["param_message"] == "test"
    assert event["log"]["logger_name"] == "foo"
    assert event["log"]["level"] == "info"
    assert "exception" not in event


def test_404_middleware(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.Catch404Middleware"])
    ):
        resp = client.get("/non-existant-page")
        assert resp.status_code == 404

        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]

        assert event["log"]["level"] == "info"
        assert event["log"]["logger_name"] == "http404"

        assert "request" in event["context"]
        request = event["context"]["request"]
        assert request["url"]["full"] == u"http://testserver/non-existant-page"
        assert request["method"] == "GET"
        assert "body" not in request


def test_404_middleware_with_debug(django_elasticapm_client, client):
    django_elasticapm_client.config.debug = False
    with override_settings(
        DEBUG=True, **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.Catch404Middleware"])
    ):
        resp = client.get("/non-existant-page")
        assert resp.status_code == 404
        assert len(django_elasticapm_client.events) == 0


def test_response_error_id_middleware(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(
            django.VERSION,
            [
                "elasticapm.contrib.django.middleware.ErrorIdMiddleware",
                "elasticapm.contrib.django.middleware.Catch404Middleware",
            ],
        )
    ):
        resp = client.get("/non-existant-page")
        assert resp.status_code == 404
        headers = dict(resp.items())
        assert "X-ElasticAPM-ErrorId" in headers
        assert len(django_elasticapm_client.events[ERROR]) == 1
        event = django_elasticapm_client.events[ERROR][0]
        assert event["id"] == headers["X-ElasticAPM-ErrorId"]


def test_get_client(django_elasticapm_client):
    with mock.patch.dict("os.environ", {"ELASTIC_APM_METRICS_INTERVAL": "0ms"}):
        client2 = get_client("elasticapm.base.Client")
        try:
            assert get_client() is get_client()
            assert client2.__class__ == Client
        finally:
            get_client().close()
            client2.close()


@pytest.mark.parametrize("django_elasticapm_client", [{"capture_body": "errors"}], indirect=True)
def test_raw_post_data_partial_read(django_elasticapm_client):
    v = compat.b('{"foo": "bar"}')
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(v + compat.b("\r\n\r\n")),
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": len(v),
            "ACCEPT": "application/json",
        }
    )
    request.read(1)

    django_elasticapm_client.capture("Message", message="foo", request=request)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["method"] == "POST"
    assert request["body"] == "<unavailable>"


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_post_data(django_elasticapm_client):
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(),
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "ACCEPT": "application/json",
        }
    )
    request.POST = QueryDict("x=1&y=2&y=3")
    django_elasticapm_client.capture("Message", message="foo", request=request)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["method"] == "POST"
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert request["body"] == {"x": "1", "y": ["2", "3"]}
    else:
        assert request["body"] == "[REDACTED]"


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_post_raw_data(django_elasticapm_client):
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(compat.b("foobar")),
            "wsgi.url_scheme": "http",
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "application/json",
            "ACCEPT": "application/json",
            "CONTENT_LENGTH": "6",
        }
    )
    django_elasticapm_client.capture("Message", message="foo", request=request)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["method"] == "POST"
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert request["body"] == compat.b("foobar")
    else:
        assert request["body"] == "[REDACTED]"


def test_post_read_error_logging(django_elasticapm_client, caplog, rf):
    request = rf.post("/test", data="{}", content_type="application/json")

    def read():
        raise IOError("foobar")

    request.read = read
    with caplog.at_level(logging.DEBUG):
        django_elasticapm_client.get_data_from_request(request, capture_body=True)
    record = caplog.records[0]
    assert record.message == "Can't capture request body: foobar"


@pytest.mark.skipif(django.VERSION < (1, 9), reason="get-raw-uri-not-available")
def test_disallowed_hosts_error_django_19(django_elasticapm_client):
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(),
            "wsgi.url_scheme": "http",
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "application/json",
            "ACCEPT": "application/json",
        }
    )
    with override_settings(ALLOWED_HOSTS=["example.com"]):
        # this should not raise a DisallowedHost exception
        django_elasticapm_client.capture("Message", message="foo", request=request)
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["request"]["url"]["full"] == "http://testserver/"


@pytest.mark.skipif(django.VERSION >= (1, 9), reason="get-raw-uri-available")
def test_disallowed_hosts_error_django_18(django_elasticapm_client):
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(),
            "wsgi.url_scheme": "http",
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "application/json",
            "ACCEPT": "application/json",
        }
    )
    with override_settings(ALLOWED_HOSTS=["example.com"]):
        # this should not raise a DisallowedHost exception
        django_elasticapm_client.capture("Message", message="foo", request=request)
    event = django_elasticapm_client.events[ERROR][0]
    assert event["context"]["request"]["url"] == {"full": "DisallowedHost"}


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_request_capture(django_elasticapm_client):
    request = WSGIRequest(
        environ={
            "wsgi.input": compat.BytesIO(),
            "REQUEST_METHOD": "POST",
            "SERVER_NAME": "testserver",
            "SERVER_PORT": "80",
            "CONTENT_TYPE": "text/html",
            "ACCEPT": "text/html",
        }
    )
    request.read(1)

    django_elasticapm_client.capture("Message", message="foo", request=request)

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]

    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["method"] == "POST"
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert request["body"] == "<unavailable>"
    else:
        assert request["body"] == "[REDACTED]"
    assert "headers" in request
    headers = request["headers"]
    assert "content-type" in headers, headers.keys()
    assert headers["content-type"] == "text/html"
    env = request["env"]
    assert "SERVER_NAME" in env, env.keys()
    assert env["SERVER_NAME"] == "testserver"
    assert "SERVER_PORT" in env, env.keys()
    assert env["SERVER_PORT"] == "80"


def test_transaction_request_response_data(django_elasticapm_client, client):
    client.cookies = SimpleCookie({"foo": "bar"})
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get(reverse("elasticapm-no-error"))
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction["result"] == "HTTP 2xx"
    assert "request" in transaction["context"]
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert "headers" in request
    headers = request["headers"]
    # cookie serialization in the test client changed in Django 2.2, see
    # https://code.djangoproject.com/ticket/29576
    assert headers["cookie"] in (" foo=bar", "foo=bar")
    env = request["env"]
    assert "SERVER_NAME" in env, env.keys()
    assert env["SERVER_NAME"] == "testserver"
    assert "SERVER_PORT" in env, env.keys()
    assert env["SERVER_PORT"] == "80"

    assert "response" in transaction["context"]
    response = transaction["context"]["response"]
    assert response["status_code"] == 200
    if "my-header" in response["headers"]:
        # Django >= 2
        assert response["headers"]["my-header"] == "foo"
    else:
        assert response["headers"]["My-Header"] == "foo"


def test_transaction_metrics(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        assert len(django_elasticapm_client.events[TRANSACTION]) == 0
        client.get(reverse("elasticapm-no-error"))
        assert len(django_elasticapm_client.events[TRANSACTION]) == 1

        transactions = django_elasticapm_client.events[TRANSACTION]

        assert len(transactions) == 1
        transaction = transactions[0]
        assert transaction["duration"] > 0
        assert transaction["result"] == "HTTP 2xx"
        assert transaction["name"] == "GET tests.contrib.django.testapp.views.no_error"


def test_transaction_metrics_debug(django_elasticapm_client, client):
    with override_settings(
        DEBUG=True, **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        assert len(django_elasticapm_client.events[TRANSACTION]) == 0
        client.get(reverse("elasticapm-no-error"))
        assert len(django_elasticapm_client.events[TRANSACTION]) == 0


@pytest.mark.parametrize("django_elasticapm_client", [{"debug": True}], indirect=True)
def test_transaction_metrics_debug_and_client_debug(django_elasticapm_client, client):
    assert django_elasticapm_client.config.debug is True

    with override_settings(
        DEBUG=True, **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        assert len(django_elasticapm_client.events[TRANSACTION]) == 0
        client.get(reverse("elasticapm-no-error"))
        assert len(django_elasticapm_client.events[TRANSACTION]) == 1


def test_request_metrics_301_append_slash(django_elasticapm_client, client):
    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True

    from elasticapm.contrib.django.middleware import TracingMiddleware

    TracingMiddleware._elasticapm_instrumented = False

    with override_settings(
        APPEND_SLASH=True,
        **middleware_setting(
            django.VERSION,
            ["elasticapm.contrib.django.middleware.TracingMiddleware", "django.middleware.common.CommonMiddleware"],
        )
    ):
        client.get(reverse("elasticapm-no-error-slash")[:-1])
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert transactions[0]["name"] in (
        # django <= 1.8
        "GET django.middleware.common.CommonMiddleware.process_request",
        # django 1.9+
        "GET django.middleware.common.CommonMiddleware.process_response",
    )
    assert transactions[0]["result"] == "HTTP 3xx"


def test_request_metrics_301_prepend_www(django_elasticapm_client, client):
    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True

    from elasticapm.contrib.django.middleware import TracingMiddleware

    TracingMiddleware._elasticapm_instrumented = False

    with override_settings(
        PREPEND_WWW=True,
        **middleware_setting(
            django.VERSION,
            ["elasticapm.contrib.django.middleware.TracingMiddleware", "django.middleware.common.CommonMiddleware"],
        )
    ):
        client.get(reverse("elasticapm-no-error"))
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert transactions[0]["name"] == "GET django.middleware.common.CommonMiddleware.process_request"
    assert transactions[0]["result"] == "HTTP 3xx"


@pytest.mark.django_db
def test_request_metrics_contrib_redirect(django_elasticapm_client, client):
    # enable middleware wrapping
    django_elasticapm_client.config.instrument_django_middleware = True
    from elasticapm.contrib.django.middleware import TracingMiddleware

    TracingMiddleware._elasticapm_instrumented = False

    s = Site.objects.get(pk=1)
    Redirect.objects.create(site=s, old_path="/redirect/me/", new_path="/here/")

    with override_settings(
        **middleware_setting(
            django.VERSION,
            [
                "elasticapm.contrib.django.middleware.TracingMiddleware",
                "django.contrib.redirects.middleware.RedirectFallbackMiddleware",
            ],
        )
    ):
        response = client.get("/redirect/me/")

    transactions = django_elasticapm_client.events[TRANSACTION]
    assert (
        transactions[0]["name"] == "GET django.contrib.redirects.middleware.RedirectFallbackMiddleware.process_response"
    )
    assert transactions[0]["result"] == "HTTP 3xx"


def test_request_metrics_404_resolve_error(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get("/i-dont-exist/")
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert transactions[0]["name"] == ""


@pytest.mark.django_db
def test_request_metrics_streaming(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        resp = client.get(reverse("elasticapm-streaming-view"))
        assert list(resp.streaming_content) == [b"0", b"1", b"2", b"3", b"4"]
        resp.close()
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["duration"] >= 50

    spans = django_elasticapm_client.events[SPAN]
    assert len(spans) == 5


def test_request_metrics_name_override(django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get(reverse("elasticapm-name-override"))
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["name"] == "foo"
    assert transaction["result"] == "okydoky"


@pytest.mark.parametrize("middleware_attr", ["MIDDLEWARE", "MIDDLEWARE_CLASSES"])
def test_tracing_middleware_autoinsertion_list(middleware_attr):
    settings = mock.Mock(spec=[middleware_attr], **{middleware_attr: ["a", "b", "c"]})
    ElasticAPMConfig.insert_middleware(settings)
    middleware_list = getattr(settings, middleware_attr)
    assert len(middleware_list) == 4
    assert middleware_list[0] == "elasticapm.contrib.django.middleware.TracingMiddleware"
    assert isinstance(middleware_list, list)


@pytest.mark.parametrize("middleware_attr", ["MIDDLEWARE", "MIDDLEWARE_CLASSES"])
def test_tracing_middleware_autoinsertion_tuple(middleware_attr):
    settings = mock.Mock(spec=[middleware_attr], **{middleware_attr: ("a", "b", "c")})
    ElasticAPMConfig.insert_middleware(settings)
    middleware_list = getattr(settings, middleware_attr)
    assert len(middleware_list) == 4
    assert middleware_list[0] == "elasticapm.contrib.django.middleware.TracingMiddleware"
    assert isinstance(middleware_list, tuple)


def test_tracing_middleware_autoinsertion_no_middleware_setting(caplog):
    with caplog.at_level(logging.DEBUG, logger="elasticapm.traces"):
        ElasticAPMConfig.insert_middleware(object())
    record = caplog.records[-1]
    assert "not autoinserting" in record.message


@pytest.mark.parametrize("middleware_attr", ["MIDDLEWARE", "MIDDLEWARE_CLASSES"])
def test_tracing_middleware_autoinsertion_wrong_type(middleware_attr, caplog):
    settings = mock.Mock(spec=[middleware_attr], **{middleware_attr: {"a", "b", "c"}})
    with caplog.at_level(logging.DEBUG, logger="elasticapm.traces"):
        ElasticAPMConfig.insert_middleware(settings)
    record = caplog.records[-1]
    assert "not of type list or tuple" in record.message


@pytest.mark.parametrize("header_name", [constants.TRACEPARENT_HEADER_NAME, constants.TRACEPARENT_LEGACY_HEADER_NAME])
def test_traceparent_header_handling(django_elasticapm_client, client, header_name):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ), mock.patch(
        "elasticapm.contrib.django.apps.TraceParent.from_string", wraps=TraceParent.from_string
    ) as wrapped_from_string:
        wsgi = lambda s: "HTTP_" + s.upper().replace("-", "_")
        wsgi_header_name = wsgi(header_name)
        wsgi_tracestate_name = wsgi(constants.TRACESTATE_HEADER_NAME)
        kwargs = {
            wsgi_header_name: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            wsgi_tracestate_name: "foo=bar,baz=bazzinga",
        }
        client.get(reverse("elasticapm-no-error"), **kwargs)
        transaction = django_elasticapm_client.events[TRANSACTION][0]
        assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert transaction["parent_id"] == "b7ad6b7169203331"
        assert "foo=bar,baz=bazzinga" in wrapped_from_string.call_args[0]


def test_get_service_info(django_elasticapm_client):
    app_info = django_elasticapm_client.get_service_info()
    assert django.get_version() == app_info["framework"]["version"]
    assert app_info["framework"]["name"] == "django"
    assert django_elasticapm_client.config.framework_name == "django"


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"filter_exception_types": ["KeyError", "tests.contrib.django.fake1.FakeException"]}],
    indirect=True,
)
def test_filter_no_match(django_sending_elasticapm_client):
    try:
        raise ValueError("foo")
    except ValueError:
        django_sending_elasticapm_client.capture("Exception", handled=False)
    django_sending_elasticapm_client.close()
    assert len(django_sending_elasticapm_client.httpserver.requests) == 1


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"filter_exception_types": ["KeyError", "tests.contrib.django.fake1.FakeException"]}],
    indirect=True,
)
def test_filter_matches_type(django_sending_elasticapm_client):
    try:
        raise KeyError("foo")
    except KeyError:
        django_sending_elasticapm_client.capture("Exception")
    django_sending_elasticapm_client.close()
    assert len(django_sending_elasticapm_client.httpserver.requests) == 0


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"filter_exception_types": ["KeyError", "tests.contrib.django.fake1.FakeException"]}],
    indirect=True,
)
def test_filter_matches_type_but_not_module(django_sending_elasticapm_client):
    from tests.contrib.django.fake2 import FakeException

    try:
        raise FakeException("foo")
    except FakeException:
        django_sending_elasticapm_client.capture("Exception", handled=False)
    django_sending_elasticapm_client.close()
    assert len(django_sending_elasticapm_client.httpserver.requests) == 1


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"filter_exception_types": ["KeyError", "tests.contrib.django.fake1.FakeException"]}],
    indirect=True,
)
def test_filter_matches_type_and_module(django_sending_elasticapm_client):
    from tests.contrib.django.fake1 import FakeException

    try:
        raise FakeException("foo")
    except FakeException:
        django_sending_elasticapm_client.capture("Exception", handled=False)
    django_sending_elasticapm_client.close()
    assert len(django_sending_elasticapm_client.httpserver.requests) == 0


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"filter_exception_types": ["KeyError", "tests.contrib.django.fake1.FakeException"]}],
    indirect=True,
)
def test_filter_matches_module_only(django_sending_elasticapm_client):
    from tests.contrib.django.fake1 import OtherFakeException

    try:
        raise OtherFakeException("foo")
    except OtherFakeException:
        django_sending_elasticapm_client.capture("Exception", handled=False)
    django_sending_elasticapm_client.close()
    assert len(django_sending_elasticapm_client.httpserver.requests) == 1


def test_django_logging_request_kwarg(django_elasticapm_client):
    handler = LoggingHandler()

    logger = logging.getLogger(__name__)
    logger.handlers = []
    logger.addHandler(handler)

    logger.error(
        "This is a test error",
        extra={
            "request": WSGIRequest(
                environ={
                    "wsgi.input": compat.StringIO(),
                    "REQUEST_METHOD": "POST",
                    "SERVER_NAME": "testserver",
                    "SERVER_PORT": "80",
                    "CONTENT_TYPE": "application/json",
                    "ACCEPT": "application/json",
                }
            )
        },
    )

    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "request" in event["context"]
    request = event["context"]["request"]
    assert request["method"] == "POST"


def test_django_logging_middleware(django_elasticapm_client, client):
    handler = LoggingHandler()

    logger = logging.getLogger("logmiddleware")
    logger.handlers = []
    logger.addHandler(handler)
    logger.level = logging.INFO

    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.LogMiddleware"])
    ):
        client.get(reverse("elasticapm-logging"))
    assert len(django_elasticapm_client.events[ERROR]) == 1
    event = django_elasticapm_client.events[ERROR][0]
    assert "request" in event["context"]
    assert event["context"]["request"]["url"]["pathname"] == reverse("elasticapm-logging")


def client_get(client, url):
    return client.get(url)


def test_stacktraces_have_templates(client, django_elasticapm_client):
    # only Django 1.9+ have the necessary information stored on Node/Template
    # instances when TEMPLATE_DEBUG = False

    TEMPLATE_DEBUG = django.VERSION < (1, 9)

    TEMPLATES_copy = deepcopy(settings.TEMPLATES)
    TEMPLATES_copy[0]["OPTIONS"]["debug"] = TEMPLATE_DEBUG
    with override_settings(
        TEMPLATE_DEBUG=TEMPLATE_DEBUG,
        TEMPLATES=TEMPLATES_copy,
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = django_elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction["result"] == "HTTP 2xx"
    spans = django_elasticapm_client.events[SPAN]
    assert len(spans) == 2, [t["name"] for t in spans]

    expected_names = {"list_users.html", "something_expensive"}

    assert {t["name"] for t in spans} == expected_names

    assert spans[0]["name"] == "something_expensive"

    # Find the template
    for frame in spans[0]["stacktrace"]:
        if frame["lineno"] == 4 and frame["filename"].endswith(
            os.path.join("django", "testapp", "templates", "list_users.html")
        ):
            break
    else:
        assert False is True, "Template was not found"


def test_stacktrace_filtered_for_elasticapm(client, django_elasticapm_client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        resp = client.get(reverse("render-heavy-template"))
    assert resp.status_code == 200

    transactions = django_elasticapm_client.events[TRANSACTION]
    assert transactions[0]["result"] == "HTTP 2xx"
    spans = django_elasticapm_client.events[SPAN]

    expected_signatures = ["transaction", "list_users.html", "something_expensive"]

    assert spans[1]["name"] == "list_users.html"

    # Top frame should be inside django rendering
    assert spans[1]["stacktrace"][0]["module"].startswith("django.template"), spans[1]["stacktrace"][0]["function"]


@pytest.mark.skipif(django.VERSION > (1, 7), reason="argparse raises CommandError in this case")
@mock.patch("elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv")
def test_subcommand_not_set(argv_mock):
    stdout = compat.StringIO()
    argv_mock.return_value = ["manage.py", "elasticapm"]
    call_command("elasticapm", stdout=stdout)
    output = stdout.getvalue()
    assert "No command specified" in output


@mock.patch("elasticapm.contrib.django.management.commands.elasticapm.Command._get_argv")
def test_subcommand_not_known(argv_mock):
    stdout = compat.StringIO()
    argv_mock.return_value = ["manage.py", "elasticapm"]
    call_command("elasticapm", "foo", stdout=stdout)
    output = stdout.getvalue()
    assert 'No such command "foo"' in output


def test_settings_missing():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Configuration errors detected" in output
    assert "SERVICE_NAME not set" in output
    assert "optional SECRET_TOKEN not set" in output


def test_settings_missing_secret_token_no_https():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": "http://foo"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "optional SECRET_TOKEN not set" in output


def test_settings_secret_token_https():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SECRET_TOKEN": "foo", "SERVER_URL": "https://foo"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "SECRET_TOKEN not set" not in output


def test_middleware_not_set():
    stdout = compat.StringIO()
    with override_settings(**middleware_setting(django.VERSION, ())):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Tracing middleware not configured!" in output
    if django.VERSION < (1, 10):
        assert "MIDDLEWARE_CLASSES" in output
    else:
        assert "MIDDLEWARE setting" in output


def test_middleware_not_first():
    stdout = compat.StringIO()
    with override_settings(
        **middleware_setting(django.VERSION, ("foo", "elasticapm.contrib.django.middleware.TracingMiddleware"))
    ):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "not at the first position" in output
    if django.VERSION < (1, 10):
        assert "MIDDLEWARE_CLASSES" in output
    else:
        assert "MIDDLEWARE setting" in output


def test_settings_server_url_default():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "SERVER_URL http://localhost:8200 looks fine" in output


def test_settings_server_url_is_empty_string():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": ""}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Configuration errors detected" in output
    assert "SERVER_URL appears to be empty" in output


def test_settings_server_url_not_http_nor_https():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": "xhttp://dev.brwnppr.com:8000/"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Configuration errors detected" in output
    assert "SERVER_URL has scheme xhttp and we require http or https" in output


def test_settings_server_url_uppercase_http():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": "HTTP://dev.brwnppr.com:8000/"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "SERVER_URL HTTP://dev.brwnppr.com:8000/ looks fine" in output


def test_settings_server_url_with_at():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": "http://y@dev.brwnppr.com:8000/"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Configuration errors detected" in output
    assert "SERVER_URL contains an unexpected at-sign!" in output


def test_settings_server_url_with_credentials():
    stdout = compat.StringIO()
    with override_settings(ELASTIC_APM={"SERVER_URL": "http://x:y@dev.brwnppr.com:8000/"}):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "Configuration errors detected" in output
    assert "SERVER_URL cannot contain authentication credentials" in output


@pytest.mark.skipif(
    not ((1, 10) <= django.VERSION < (2, 0)),
    reason="only needed in 1.10 and 1.11 when both middleware settings are valid",
)
def test_django_1_10_uses_deprecated_MIDDLEWARE_CLASSES():
    stdout = compat.StringIO()
    with override_settings(
        MIDDLEWARE=None, MIDDLEWARE_CLASSES=["foo", "elasticapm.contrib.django.middleware.TracingMiddleware"]
    ):
        call_command("elasticapm", "check", stdout=stdout)
    output = stdout.getvalue()
    assert "not at the first position" in output


@mock.patch("elasticapm.transport.http.urllib3.PoolManager.urlopen")
def test_test_exception(urlopen_mock):
    stdout = compat.StringIO()
    resp = mock.Mock(status=200, getheader=lambda h: "http://example.com")
    urlopen_mock.return_value = resp
    with override_settings(
        **middleware_setting(django.VERSION, ["foo", "elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        call_command("elasticapm", "test", stdout=stdout, stderr=stdout)
    output = stdout.getvalue()
    assert "Success! We tracked the error successfully!" in output


def test_tracing_middleware_uses_test_client(client, django_elasticapm_client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get("/")
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert len(transactions) == 1
    assert transactions[0]["context"]["request"]["url"]["pathname"] == "/"


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "transactions"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_capture_post_errors_dict(client, django_elasticapm_client):
    with pytest.raises(MyException):
        client.post(reverse("elasticapm-raise-exc"), {"username": "john", "password": "smith"})
    error = django_elasticapm_client.events[ERROR][0]
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert error["context"]["request"]["body"] == {"username": "john", "password": "smith"}
    else:
        assert error["context"]["request"]["body"] == "[REDACTED]"


def test_capture_body_config_is_dynamic_for_errors(client, django_elasticapm_client):
    django_elasticapm_client.config.update(version="1", capture_body="all")
    with pytest.raises(MyException):
        client.post(reverse("elasticapm-raise-exc"), {"username": "john", "password": "smith"})
    error = django_elasticapm_client.events[ERROR][0]
    assert error["context"]["request"]["body"] == {"username": "john", "password": "smith"}

    django_elasticapm_client.config.update(version="1", capture_body="off")
    with pytest.raises(MyException):
        client.post(reverse("elasticapm-raise-exc"), {"username": "john", "password": "smith"})
    error = django_elasticapm_client.events[ERROR][1]
    assert error["context"]["request"]["body"] == "[REDACTED]"


def test_capture_body_config_is_dynamic_for_transactions(client, django_elasticapm_client):
    django_elasticapm_client.config.update(version="1", capture_body="all")
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.post(reverse("elasticapm-no-error"), {"username": "john", "password": "smith"})
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["context"]["request"]["body"] == {"username": "john", "password": "smith"}

    django_elasticapm_client.config.update(version="1", capture_body="off")
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.post(reverse("elasticapm-no-error"), {"username": "john", "password": "smith"})
    transaction = django_elasticapm_client.events[TRANSACTION][1]
    assert transaction["context"]["request"]["body"] == "[REDACTED]"


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "transactions"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_capture_post_errors_multivalue_dict(client, django_elasticapm_client):
    with pytest.raises(MyException):
        client.post(
            reverse("elasticapm-raise-exc"),
            "key=value1&key=value2&test=test&key=value3",
            content_type="application/x-www-form-urlencoded",
        )
    error = django_elasticapm_client.events[ERROR][0]
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert error["context"]["request"]["body"] == {"key": ["value1", "value2", "value3"], "test": "test"}
    else:
        assert error["context"]["request"]["body"] == "[REDACTED]"


@pytest.mark.parametrize(
    "django_sending_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "transactions"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_capture_post_errors_raw(client, django_sending_elasticapm_client):
    # use "sending" client to ensure that we encode the payload correctly
    with pytest.raises(MyException):
        client.post(
            reverse("elasticapm-raise-exc"), json.dumps({"a": "b"}), content_type="application/json; charset=utf8"
        )
    django_sending_elasticapm_client.close()
    error = django_sending_elasticapm_client.httpserver.payloads[0][1]["error"]
    if django_sending_elasticapm_client.config.capture_body in ("errors", "all"):
        assert error["context"]["request"]["body"] == '{"a": "b"}'
    else:
        assert error["context"]["request"]["body"] == "[REDACTED]"


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "transactions"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_capture_empty_body(client, django_elasticapm_client):
    with pytest.raises(MyException):
        client.post(reverse("elasticapm-raise-exc"), data={})
    error = django_elasticapm_client.events[ERROR][0]
    # body should be empty no matter if we capture it or not
    assert error["context"]["request"]["body"] == {}


@pytest.mark.parametrize(
    "django_elasticapm_client",
    [{"capture_body": "errors"}, {"capture_body": "transactions"}, {"capture_body": "all"}, {"capture_body": "off"}],
    indirect=True,
)
def test_capture_files(client, django_elasticapm_client):
    with pytest.raises(MyException), open(os.path.abspath(__file__)) as f:
        client.post(
            reverse("elasticapm-raise-exc"), data={"a": "b", "f1": compat.BytesIO(100 * compat.b("1")), "f2": f}
        )
    error = django_elasticapm_client.events[ERROR][0]
    if django_elasticapm_client.config.capture_body in ("errors", "all"):
        assert error["context"]["request"]["body"] == {"a": "b", "_files": {"f1": "f1", "f2": "django_tests.py"}}
    else:
        assert error["context"]["request"]["body"] == "[REDACTED]"


@pytest.mark.parametrize(
    "django_elasticapm_client", [{"capture_headers": "true"}, {"capture_headers": "false"}], indirect=True
)
def test_capture_headers(client, django_elasticapm_client):
    with pytest.raises(MyException), override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.post(reverse("elasticapm-raise-exc"), **{"HTTP_SOME_HEADER": "foo"})
    error = django_elasticapm_client.events[ERROR][0]
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    if django_elasticapm_client.config.capture_headers:
        assert error["context"]["request"]["headers"]["some-header"] == "foo"
        assert transaction["context"]["request"]["headers"]["some-header"] == "foo"
        assert "headers" in transaction["context"]["response"]
    else:
        assert "headers" not in error["context"]["request"]
        assert "headers" not in transaction["context"]["request"]
        assert "headers" not in transaction["context"]["response"]


@pytest.mark.parametrize("django_elasticapm_client", [{"capture_body": "transactions"}], indirect=True)
def test_options_request(client, django_elasticapm_client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.options("/")
    transactions = django_elasticapm_client.events[TRANSACTION]
    assert transactions[0]["context"]["request"]["method"] == "OPTIONS"


def test_rum_tracing_context_processor(client, django_elasticapm_client):
    with override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [BASE_TEMPLATE_DIR],
                "OPTIONS": {
                    "context_processors": [
                        "django.contrib.auth.context_processors.auth",
                        "elasticapm.contrib.django.context_processors.rum_tracing",
                    ],
                    "loaders": ["django.template.loaders.filesystem.Loader"],
                    "debug": False,
                },
            }
        ],
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        response = client.get(reverse("render-heavy-template"))
        transactions = django_elasticapm_client.events[TRANSACTION]
        assert response.context["apm"]["trace_id"] == transactions[0]["trace_id"]
        assert response.context["apm"]["is_sampled"]
        assert response.context["apm"]["is_sampled_js"] == "true"
        assert callable(response.context["apm"]["span_id"])


@pytest.mark.skipif(django.VERSION < (2, 2), reason="ResolverMatch.route attribute is new in Django 2.2")
@pytest.mark.parametrize("django_elasticapm_client", [{"django_transaction_name_from_route": "true"}], indirect=True)
def test_transaction_name_from_route(client, django_elasticapm_client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get("/route/1/")
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["name"] == "GET route/<int:id>/"


@pytest.mark.skipif(django.VERSION >= (2, 2), reason="ResolverMatch.route attribute is new in Django 2.2")
@pytest.mark.parametrize("django_elasticapm_client", [{"django_transaction_name_from_route": "true"}], indirect=True)
def test_transaction_name_from_route_doesnt_have_effect_in_older_django(client, django_elasticapm_client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get("/no-error")
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["name"] == "GET tests.contrib.django.testapp.views.no_error"
