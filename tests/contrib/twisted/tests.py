from __future__ import absolute_import

from twisted.python.failure import Failure

from opbeat.contrib.twisted import OpbeatLogObserver
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class TwistedLogObserverTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()

    def test_observer(self):
        observer = OpbeatLogObserver(client=self.client)
        try:
            1 / 0
        except ZeroDivisionError:
            failure = Failure()
        event = dict(log_failure=failure)
        observer(event)

        cli_event = self.client.events.pop(0)
        self.assertEquals(cli_event['exception']['type'], 'ZeroDivisionError')
        self.assertTrue('zero' in cli_event['exception']['value'])
