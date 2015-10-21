# -*- coding: utf-8 -*-
from __future__ import absolute_import

import mock
import pytest

from opbeat.contrib.celery import CeleryClient
from tests.utils.compat import TestCase

try:
    from celery.tests.utils import with_eager_tasks
    has_with_eager_tasks = True
except ImportError:
    from opbeat.utils.compat import noop_decorator as with_eager_tasks
    has_with_eager_tasks = False


class ClientTest(TestCase):
    def setUp(self):
        self.client = CeleryClient(
            organization_id='organization_id',
            app_id='app_id',
            secret_token='secret'
        )

    @mock.patch('opbeat.contrib.celery.CeleryClient.send_raw')
    def test_send_encoded(self, send_raw):
        self.client.send_encoded('foo')

        send_raw.delay.assert_called_once_with('foo')

    @mock.patch('opbeat.contrib.celery.CeleryClient.send_raw')
    def test_without_eager(self, send_raw):
        """
        Integration test to ensure it propagates all the way down
        and calls delay on the task.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_raw.delay.call_count, 1)

    @pytest.mark.skipif(not has_with_eager_tasks,
                        reason='with_eager_tasks is not available')
    @with_eager_tasks
    @mock.patch('opbeat.base.Client.send_encoded')
    def test_with_eager(self, send_encoded):
        """
        Integration test to ensure it propagates all the way down
        and calls the parent client's send_encoded method.
        """
        self.client.capture('Message', message='test')

        self.assertEquals(send_encoded.call_count, 1)
