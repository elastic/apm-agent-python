# -*- coding: utf-8 -*-
import pytest  # isort:skip
django = pytest.importorskip("django")  # isort:skip
celery = pytest.importorskip("celery")  # isort:skip

import mock

from elasticapm.contrib.celery import (register_exception_tracking,
                                       register_instrumentation)
from tests.contrib.django.testapp.tasks import failing_task, successful_task

pytestmark = pytest.mark.celery


def test_failing_celery_task(django_elasticapm_client):
    register_exception_tracking(django_elasticapm_client)
    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect_mock:
        should_collect_mock.return_value = True
        t = failing_task.delay()
    assert t.state == 'FAILURE'
    assert len(django_elasticapm_client.events) == 2
    error = django_elasticapm_client.events[0]['errors'][0]
    assert error['culprit'] == 'tests.contrib.django.testapp.tasks.failing_task'
    assert error['exception']['message'] == 'ValueError: foo'
    assert error['exception']['handled'] is False

    transaction = django_elasticapm_client.events[1]['transactions'][0]
    assert transaction['name'] == 'tests.contrib.django.testapp.tasks.failing_task'
    assert transaction['type'] == 'celery'
    assert transaction['result'] == 'FAILURE'


def test_successful_celery_task_instrumentation(django_elasticapm_client):
    register_instrumentation(django_elasticapm_client)
    with mock.patch('elasticapm.traces.TransactionsStore.should_collect') as should_collect_mock:
        should_collect_mock.return_value = True
        t = successful_task.delay()
    assert t.state == 'SUCCESS'
    assert len(django_elasticapm_client.events[0]['transactions']) == 1
    transaction = django_elasticapm_client.events[0]['transactions'][0]
    assert transaction['name'] == 'tests.contrib.django.testapp.tasks.successful_task'
    assert transaction['type'] == 'celery'
    assert transaction['result'] == 'SUCCESS'
