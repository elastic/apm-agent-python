from __future__ import absolute_import

from twisted.python.failure import Failure

from elasticapm.contrib.twisted import LogObserver


def test_twisted_log_observer(elasticapm_client):
    observer = LogObserver(client=elasticapm_client)
    try:
        1 / 0
    except ZeroDivisionError:
        failure = Failure()
    event = dict(log_failure=failure)
    observer(event)

    cli_event = elasticapm_client.events.pop(0)['errors'][0]
    assert cli_event['exception']['type'] == 'ZeroDivisionError'
