#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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


import logging
import os
import sys
import time
from threading import Lock, Thread

from elasticapm.utils.compat import queue

logger = logging.getLogger("elasticapm")

ELASTIC_APM_WAIT_SECONDS = 10


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

                sys.stdout.write("PID %i: ElasticAPM is attempting to send %i pending messages\n" % (os.getpid(), size))
                sys.stdout.write("Waiting up to %s seconds, " % ELASTIC_APM_WAIT_SECONDS)
                wait_start = time.time()
                if os.name == "nt":
                    sys.stdout.write("press Ctrl-Break to quit.\n")
                else:
                    sys.stdout.write("press Ctrl-C to quit.\n")
                self._timed_queue_join(ELASTIC_APM_WAIT_SECONDS - initial_timeout)
                sys.stdout.write(
                    "PID %i: done, took %.2f seconds to complete.\n" % (os.getpid(), time.time() - wait_start)
                )
            self._thread = None

        finally:
            self._lock.release()

    def _timed_queue_join(self, timeout):
        """
        implementation of Queue.join which takes a 'timeout' argument

        returns True on success, False on timeout
        """
        deadline = time.time() + timeout

        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                delay = deadline - time.time()
                if delay <= 0:
                    # timed out
                    return False

                self._queue.all_tasks_done.wait(timeout=delay)

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
                self._thread.name = "elasticapm sender thread"
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
                    logger.error("Error while sending", exc_info=True)
            finally:
                self._queue.task_done()
            time.sleep(0)


class Worker(object):
    """
    A WSGI middleware which provides ``environ['elasticapm.worker']``
    that can be used by clients to process asynchronous tasks.

    >>> from elasticapm.base import Client
    >>> application = Worker(application)
    """

    def __init__(self, application):
        self.application = application
        self.worker = AsyncWorker()

    def __call__(self, environ, start_response):
        environ["elasticapm.worker"] = self.worker
        for event in self.application(environ, start_response):
            yield event
