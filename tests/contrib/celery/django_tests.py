# -*- coding: utf-8 -*-
import pytest  # isort:skip
django = pytest.importorskip("django")  # isort:skip

import mock

from elasticapm.contrib.celery import (register_exception_tracking,
                                       register_instrumentation)
from tests.contrib.django.testapp.tasks import failing_task, successful_task
from tests.fixtures import test_client


def test_failing_celery_task(test_client):
    register_exception_tracking(test_client)
    t = failing_task.delay()
    assert t.state == 'FAILURE'
    assert len(test_client.events) == 1
    error = test_client.events[0]['errors'][0]
    assert error['culprit'] == 'tests.contrib.django.testapp.tasks.failing_task'
    assert error['exception']['message'] == 'ValueError: foo'


def test_successful_celery_task_instrumentation(test_client):
    register_instrumentation(test_client)
    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect_mock:
        should_collect_mock.return_value = True
        t = successful_task.delay()
    assert t.state == 'SUCCESS'
    assert len(test_client.events[0]['transactions']) == 1
    transaction = test_client.events[0]['transactions'][0]
    assert transaction['name'] == 'tests.contrib.django.testapp.tasks.successful_task'
    assert transaction['type'] == 'celery'
