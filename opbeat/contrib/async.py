"""
opbeat.contrib.async
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
import logging
import os
import time
from threading import Thread, Lock

from opbeat.utils.compat import atexit_register
from opbeat.utils import six
from opbeat.utils.six.moves import queue

logger = logging.getLogger('opbeat')

OPBEAT_WAIT_SECONDS = 10


class AsyncWorker(object):
    _terminator = object()

    def __init__(self):
        self._queue = queue.Queue(-1)
        self._lock = Lock()
        self._thread = None
        self.start()

    def main_thread_terminated(self):
        size = self._queue.qsize()
        if size:
            six.print_("Opbeat attempts to send %s error messages" % size)
            six.print_("Waiting up to %s seconds" % OPBEAT_WAIT_SECONDS)
            if os.name == 'nt':
                six.print_("Press Ctrl-Break to quit")
            else:
                six.print_("Press Ctrl-C to quit")
            self.stop(timeout=OPBEAT_WAIT_SECONDS)

    def start(self):
        """
        Starts the task thread.
        """
        self._lock.acquire()
        try:
            if not self._thread:
                self._thread = Thread(target=self._target)
                self._thread.setDaemon(True)
                self._thread.start()
        finally:
            self._lock.release()
            atexit_register(self.main_thread_terminated)

    def stop(self, timeout=None):
        """
        Stops the task thread. Synchronous!
        """
        self._lock.acquire()
        try:
            if self._thread:
                self._queue.put_nowait(self._terminator)
                self._thread.join(timeout=timeout)
                self._thread = None
        finally:
            self._lock.release()

    def queue(self, callback, kwargs):
        self._queue.put_nowait((callback, kwargs))

    def _target(self):
        while 1:
            record = self._queue.get()
            if record is self._terminator:
                break
            callback, kwargs = record
            try:
                callback(**kwargs)
            except Exception:
                logger.error('Error while sending', exc_info=True)
            finally:
                self._queue.task_done()
            time.sleep(0)


class OpbeatWorker(object):
    """
    A WSGI middleware which provides ``environ['opbeat.worker']``
    that can be used by clients to process asynchronous tasks.

    >>> from opbeat.base import Client
    >>> application = OpbeatWorker(application)
    """
    def __init__(self, application):
        self.application = application
        self.worker = AsyncWorker()

    def __call__(self, environ, start_response):
        environ['opbeat.worker'] = self.worker
        for event in self.application(environ, start_response):
            yield event
