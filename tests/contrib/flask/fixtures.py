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

import logging
import time

import pytest
from flask import Flask, Response, make_response, render_template, signals
from pytest_localserver.http import WSGIServer

import elasticapm
from elasticapm.contrib.flask import ElasticAPM


@pytest.fixture()
def flask_app():
    app = Flask(__name__)

    @app.route("/an-error/", methods=["GET", "POST"])
    def an_error():
        raise ValueError("hello world")

    @app.route("/users/", methods=["GET", "POST"])
    def users():
        response = make_response(render_template("users.html", users=["Ron", "Rasmus"]))
        response.headers.add("foo", "bar")
        response.headers.add("foo", "baz")
        response.headers.add("bar", "bazzinga")
        return response

    @app.route("/non-standard-status/", methods=["GET", "POST"])
    def non_standard_status():
        return "foo", "fail"

    @app.route("/streaming/", methods=["GET"])
    def streaming():
        def generator():
            for i in range(5):
                with elasticapm.capture_span("generator"):
                    time.sleep(0.01)
                    yield str(i)

        return Response(generator(), mimetype="text/plain")

    @app.route("/transaction-name/", methods=["GET"])
    def transaction_name():
        elasticapm.set_transaction_name("foo")
        elasticapm.set_transaction_result("okydoky")
        return Response("")

    return app


@pytest.fixture()
def flask_wsgi_server(request, flask_app, elasticapm_client):
    server = WSGIServer(application=flask_app)
    apm_client = ElasticAPM(app=flask_app, client=elasticapm_client)
    flask_app.apm_client = apm_client
    server.start()
    try:
        yield server
    finally:
        server.stop()
        apm_client.client.close()


@pytest.fixture()
def flask_apm_client(request, flask_app, elasticapm_client):
    client_config = getattr(request, "param", {})
    client_config.setdefault("app", flask_app)
    client_config.setdefault("client", elasticapm_client)
    client = ElasticAPM(**client_config)
    try:
        yield client
    finally:
        signals.request_started.disconnect(client.request_started)
        signals.request_finished.disconnect(client.request_finished)
        # remove logging handler if it was added
        logger = logging.getLogger()
        for handler in list(logger.handlers):
            if getattr(handler, "client", None) is client.client:
                logger.removeHandler(handler)


@pytest.fixture()
def sending_flask_apm_client(request, flask_app, sending_elasticapm_client):
    client_config = getattr(request, "param", {})
    client_config.setdefault("app", flask_app)
    client_config.setdefault("client", sending_elasticapm_client)
    client = ElasticAPM(**client_config)
    try:
        yield client
    finally:
        signals.request_started.disconnect(client.request_started)
        signals.request_finished.disconnect(client.request_finished)
        # remove logging handler if it was added
        logger = logging.getLogger()
        for handler in list(logger.handlers):
            if getattr(handler, "client", None) is client.client:
                logger.removeHandler(handler)


@pytest.fixture()
def flask_celery(flask_apm_client):
    from celery import Celery

    flask_app = flask_apm_client.app
    celery = Celery(flask_app.import_name, backend=None, broker=None)
    celery.conf.update(CELERY_ALWAYS_EAGER=True)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    celery.flask_apm_client = flask_apm_client
    return celery
