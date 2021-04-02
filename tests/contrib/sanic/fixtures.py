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

sanic = pytest.importorskip("sanic")  # isort:skip

import logging
import time
import typing as t

import pytest
from sanic import Sanic
from sanic.blueprints import Blueprint
from sanic.handlers import ErrorHandler
from sanic.request import Request
from sanic.response import HTTPResponse, json

import elasticapm
from elasticapm import async_capture_span
from elasticapm.contrib.sanic import ElasticAPM


class CustomException(Exception):
    pass


class CustomErrorHandler(ErrorHandler):
    def __init__(self):
        super(CustomErrorHandler, self).__init__()

    def default(self, request, exception):
        return json({"source": "custom-handler-default"}, 500)


@pytest.fixture()
def sanic_app_with_error_handler(elasticapm_client):
    app = Sanic(name="elastic-apm-custom-error", error_handler=CustomErrorHandler())
    _ = ElasticAPM(app=app, client=elasticapm_client)
    try:
        from sanic_testing import TestManager

        TestManager(app=app)
    except ImportError:
        from sanic.testing import SanicTestClient as TestManager

    @app.exception(ValueError)
    async def handle_value_error(request, exception):
        return json({"source": "value-error-custom"}, status=500)

    async def attribute_error_handler(request, expception):
        return json({"source": "custom-handler"}, status=500)

    app.error_handler.add(AttributeError, attribute_error_handler)

    @app.get("/raise-exception")
    async def raise_exception(request):
        raise AttributeError

    @app.get("/fallback-default-error")
    async def raise_default_error(request):
        raise CustomException

    @app.get("/raise-value-error")
    async def raise_value_error(request):
        raise ValueError

    try:
        yield app
    finally:
        elasticapm.uninstrument()


@pytest.fixture()
def sanic_app_with_custom_config(request, temp_store_client):
    client_config = getattr(request, "param", {})
    client_config.setdefault("service_name", "myapp")
    client_config.setdefault("secret_token", "test_key")
    client_config.setdefault("central_config", "false")
    client_config.setdefault("include_paths", ("*/tests/*",))
    client_config.setdefault("span_frames_min_duration", -1)
    client_config.setdefault("metrics_interval", "0ms")
    client_config.setdefault("cloud_provider", False)
    client_config.setdefault("processors", ("elasticapm.processors.sanitize_http_headers"))
    app = Sanic(name="elastic-apm-custom-cfg")
    apm = ElasticAPM(app=app, client_cls=temp_store_client, config=client_config)

    @app.get("/add-custom-headers")
    async def custom_headers(request):
        return json({"data": "message"}, headers={"sessionid": 1234555})

    try:
        yield app, apm
    finally:
        elasticapm.uninstrument()


@pytest.fixture()
def sanic_app(elasticapm_client):
    app = Sanic(name="elastic-apm")
    apm = ElasticAPM(app=app, client=elasticapm_client)
    try:
        from sanic_testing import TestManager

        TestManager(app=app)
    except ImportError:
        from sanic.testing import SanicTestClient as TestManager

    TestManager(app=app)

    bp = Blueprint(name="test", url_prefix="/apm", version="v1")

    @app.exception(Exception)
    def handler(request, exception):
        return json({"response": str(exception)}, 500)

    @bp.post("/unhandled-exception")
    async def raise_something(request):
        raise CustomException("Unhandled")

    @app.route("/", methods=["GET", "POST"])
    def default_route(request: Request):
        with async_capture_span("test"):
            pass
        return json({"response": "ok"})

    @app.get("/greet/<name:str>")
    async def greet_person(request: Request, name: str):
        return json({"response": f"Hello {name}"})

    @app.get("/capture-exception")
    async def capture_exception(request):
        try:
            1 / 0
        except ZeroDivisionError:
            await apm.capture_exception()
        return json({"response": "invalid"}, 500)

    app.blueprint(blueprint=bp)

    try:
        yield app
    finally:
        elasticapm.uninstrument()
