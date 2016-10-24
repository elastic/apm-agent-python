from twisted.logger import ILogObserver
from zope.interface import implementer

from opbeat.base import Client


@implementer(ILogObserver)
class OpbeatLogObserver(object):
    """
    A twisted log observer for Opbeat.
    Eg.:

    from opbeat.base import Client
    from twisted.logger import Logger

    client = Client(...)
    observer = OpbeatLogObserver(client=client)
    log = Logger(observer=observer)

    try:
        1 / 0
    except:
        log.failure("Math is hard!")
    """

    def __init__(self, client=None, **kwargs):
        self.client = client or Client(**kwargs)

    def __call__(self, event):
        failure = event.get('log_failure')
        if failure is not None:
            self.client.capture_exception(
                (failure.type, failure.value, failure.getTracebackObject()),
                extra=event)
