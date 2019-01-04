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
