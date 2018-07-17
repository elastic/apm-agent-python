from twisted.logger import ILogObserver
from zope.interface import implementer

from elasticapm.base import Client


@implementer(ILogObserver)
class LogObserver(object):
    """
    A twisted log observer for Elastic APM.
    Eg.:

    from elasticapm.base import Client
    from twisted.logger import Logger

    client = Client(...)
    observer = LogObserver(client=client)
    log = Logger(observer=observer)

    try:
        1 / 0
    except:
        log.failure("Math is hard!")
    """

    def __init__(self, client=None, **kwargs):
        self.client = client or Client(**kwargs)

    def __call__(self, event):
        failure = event.get("log_failure")
        if failure is not None:
            self.client.capture_exception(
                exc_info=(failure.type, failure.value, failure.getTracebackObject()), handled=False, extra=event
            )
