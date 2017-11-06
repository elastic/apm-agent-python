import pytest  # isort:skip
django = pytest.importorskip("flask")  # isort:skip

import mock


def test_task_failure(flask_celery):
    apm_client = flask_celery.flask_apm_client.client

    @flask_celery.task()
    def failing_task():
        raise ValueError('foo')

    t = failing_task.delay()
    assert t.status == 'FAILURE'
    assert len(apm_client.events[0]['errors']) == 1
    error = apm_client.events[0]['errors'][0]
    assert error['culprit'] == 'tests.contrib.celery.flask_tests.failing_task'
    assert error['exception']['message'] == 'ValueError: foo'


def test_task_instrumentation(flask_celery):
    apm_client = flask_celery.flask_apm_client.client

    @flask_celery.task()
    def successful_task():
        return 'OK'

    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect_mock:
        should_collect_mock.return_value = True
        t = successful_task.delay()

    assert t.status == 'SUCCESS'
    assert len(apm_client.events[0]['transactions']) == 1
    transaction = apm_client.events[0]['transactions'][0]
    assert transaction['name'] == 'tests.contrib.celery.flask_tests.successful_task'
    assert transaction['type'] == 'celery'
