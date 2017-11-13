import pytest
from flask import Flask, make_response, render_template, signals

from elasticapm.contrib.flask import ElasticAPM


@pytest.fixture()
def flask_app():
    app = Flask(__name__)

    @app.route('/an-error/', methods=['GET', 'POST'])
    def an_error():
        raise ValueError('hello world')

    @app.route('/users/', methods=['GET', 'POST'])
    def users():
        response = make_response(render_template('users.html', users=['Ron', 'Rasmus']))
        response.headers.add('foo', 'bar')
        response.headers.add('foo', 'baz')
        response.headers.add('bar', 'bazzinga')
        return response

    @app.route('/non-standard-status/', methods=['GET', 'POST'])
    def non_standard_status():
        return "foo", 'fail'

    return app


@pytest.fixture()
def flask_apm_client(flask_app, elasticapm_client):
    client = ElasticAPM(app=flask_app, client=elasticapm_client)
    yield client
    signals.request_started.disconnect(client.request_started)
    signals.request_finished.disconnect(client.request_finished)


@pytest.fixture()
def flask_celery(flask_apm_client):
    from celery import Celery

    flask_app = flask_apm_client.app
    celery = Celery(flask_app.import_name, backend=None,
                    broker=None)
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
