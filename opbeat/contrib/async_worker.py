"""
opbeat.contrib.async_worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (c) 2011-2012 Opbeat

Large portions are
:copyright: (c) 2010 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""
import logging
import os
import time
from threading import Lock, Thread

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
        self._lock.acquire()
        try:
            if not self._thread:
                # thread not started or already stopped - nothing to do
                return

            # wake the processing thread up
            self._queue.put_nowait(self._terminator)

            # wait briefly, initially
            initial_timeout = 0.1

            if not self._timed_queue_join(initial_timeout):
                # if that didn't work, wait a bit longer
                # NB that size is an approximation, because other threads may
                # add or remove items
                size = self._queue.qsize()

                six.print_(
                    "PID %i: Opbeat is attempting to send %i pending messages" % (
                        os.getpid(),
                        size,
                    )
                )
                six.print_(
                    "Waiting up to %s seconds, " % OPBEAT_WAIT_SECONDS,
                    end=''
                )
                wait_start = time.time()
                if os.name == 'nt':
                    six.print_("press Ctrl-Break to quit")
                else:
                    six.print_("press Ctrl-C to quit")
                self._timed_queue_join(OPBEAT_WAIT_SECONDS - initial_timeout)
                six.print_('PID %i: done, took %.2f seconds to complete' % (
                    os.getpid(),
                    time.time() - wait_start,
                ))
            self._thread = None

        finally:
            self._lock.release()

    def _timed_queue_join(self, timeout):
        """
        implementation of Queue.join which takes a 'timeout' argument

        returns True on success, False on timeout
        """
        deadline = time.time() + timeout
        queue = self._queue

        with queue.all_tasks_done:
            while queue.unfinished_tasks:
                delay = deadline - time.time()
                if delay <= 0:
                    # timed out
                    return False

                queue.all_tasks_done.wait(timeout=delay)

            return True

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

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def queue(self, callback, kwargs):
        self._queue.put_nowait((callback, kwargs))

    def _target(self):
        while True:
            try:
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
