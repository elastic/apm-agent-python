import pytest  # isort:skip
pytest.importorskip("twisted")  # isort:skip

from twisted.python.failure import Failure

from elasticapm.contrib.twisted import LogObserver

pytestmark = pytest.mark.twisted


def test_twisted_log_observer(elasticapm_client):
    observer = LogObserver(client=elasticapm_client)
    failure = None
    try:
        1 / 0
    except ZeroDivisionError:
        failure = Failure()
    event = dict(log_failure=failure)
    observer(event)

    cli_event = elasticapm_client.events.pop(0)['errors'][0]
    assert cli_event['exception']['type'] == 'ZeroDivisionError'
    assert cli_event['exception']['handled'] is False
