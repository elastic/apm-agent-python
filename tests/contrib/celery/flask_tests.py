import pytest  # isort:skip

flask = pytest.importorskip("flask")  # isort:skip
celery = pytest.importorskip("celery")  # isort:skip

import mock

from elasticapm.conf.constants import ERROR, TRANSACTION

pytestmark = pytest.mark.celery


def test_task_failure(flask_celery):
    apm_client = flask_celery.flask_apm_client.client

    @flask_celery.task()
    def failing_task():
        raise ValueError("foo")

    t = failing_task.delay()
    assert t.status == "FAILURE"
    assert len(apm_client.events[ERROR]) == 1
    error = apm_client.events[ERROR][0]
    assert error["culprit"] == "tests.contrib.celery.flask_tests.failing_task"
    assert error["exception"]["message"] == "ValueError: foo"
    assert error["exception"]["handled"] is False

    transaction = apm_client.events[TRANSACTION][0]
    assert transaction["name"] == "tests.contrib.celery.flask_tests.failing_task"
    assert transaction["type"] == "celery"
    assert transaction["result"] == "FAILURE"


def test_task_instrumentation(flask_celery):
    apm_client = flask_celery.flask_apm_client.client

    @flask_celery.task()
    def successful_task():
        return "OK"

    t = successful_task.delay()

    assert t.status == "SUCCESS"
    assert len(apm_client.events[TRANSACTION]) == 1
    transaction = apm_client.events[TRANSACTION][0]
    assert transaction["name"] == "tests.contrib.celery.flask_tests.successful_task"
    assert transaction["type"] == "celery"
    assert transaction["result"] == "SUCCESS"
