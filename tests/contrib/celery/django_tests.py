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
celery = pytest.importorskip("celery")  # isort:skip

from elasticapm.conf.constants import ERROR, TRANSACTION
from elasticapm.contrib.celery import register_exception_tracking, register_instrumentation
from tests.contrib.django.testapp.tasks import failing_task, successful_task

pytestmark = pytest.mark.celery


def test_failing_celery_task(django_elasticapm_client):
    register_exception_tracking(django_elasticapm_client)
    t = failing_task.delay()
    assert t.state == "FAILURE"
    assert len(django_elasticapm_client.events[ERROR]) == 1
    assert len(django_elasticapm_client.events[TRANSACTION]) == 1
    error = django_elasticapm_client.events[ERROR][0]
    assert error["culprit"] == "tests.contrib.django.testapp.tasks.failing_task"
    assert error["exception"]["message"] == "ValueError: foo"
    assert error["exception"]["handled"] is False

    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["name"] == "tests.contrib.django.testapp.tasks.failing_task"
    assert transaction["type"] == "celery"
    assert transaction["result"] == "FAILURE"


def test_successful_celery_task_instrumentation(django_elasticapm_client):
    register_instrumentation(django_elasticapm_client)
    t = successful_task.delay()
    assert t.state == "SUCCESS"
    assert len(django_elasticapm_client.events[TRANSACTION]) == 1
    transaction = django_elasticapm_client.events[TRANSACTION][0]
    assert transaction["name"] == "tests.contrib.django.testapp.tasks.successful_task"
    assert transaction["type"] == "celery"
    assert transaction["result"] == "SUCCESS"
