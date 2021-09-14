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

import gzip
import os
import random
import sys
import threading
import time
import timeit
from collections import defaultdict

from elasticapm.utils import compat, json_encoder
from elasticapm.utils.logging import get_logger
from elasticapm.utils.threading import ThreadManager

logger = get_logger("elasticapm.transport")


class Transport(ThreadManager):
    """
    All transport implementations need to subclass this class

    You must implement a send method..
    """

    async_mode = False

    def __init__(
        self,
        client,
        compress_level=5,
        json_serializer=json_encoder.dumps,
        queue_chill_count=500,
        queue_chill_time=1.0,
        processors=None,
        **kwargs
    ):
        """
        Create a new Transport instance

        :param compress_level: GZip compress level. If zero, no GZip compression will be used
        :param json_serializer: serializer to use for JSON encoding
        :param kwargs:
        """
        self.client = client
        self.state = TransportState()
        self._metadata = None
        self._compress_level = min(9, max(0, compress_level if compress_level is not None else 0))
        self._json_serializer = json_serializer
        self._queued_data = None
        self._event_queue = self._init_event_queue(chill_until=queue_chill_count, max_chill_time=queue_chill_time)
        self._is_chilled_queue = isinstance(self._event_queue, ChilledQueue)
        self._thread = None
        self._last_flush = timeit.default_timer()
        self._counts = defaultdict(int)
        self._flushed = threading.Event()
        self._closed = False
        self._processors = processors if processors is not None else []
        super(Transport, self).__init__()
        self.start_stop_order = sys.maxsize  # ensure that the transport thread is always started/stopped last

    @property
    def _max_flush_time(self):
        return self.client.config.api_request_time / 1000.0 if self.client else None

    @property
    def _max_buffer_size(self):
        return self.client.config.api_request_size if self.client else None

    def queue(self, event_type, data, flush=False):
        try:
            self._flushed.clear()
            kwargs = {"chill": not (event_type == "close" or flush)} if self._is_chilled_queue else {}
            self._event_queue.put((event_type, data, flush), block=False, **kwargs)

        except compat.queue.Full:
            logger.debug("Event of type %s dropped due to full event queue", event_type)

    def _process_queue(self):
        # Rebuild the metadata to capture new process information
        if self.client:
            self._metadata = self.client.build_metadata()

        buffer = self._init_buffer()
        buffer_written = False
        # add some randomness to timeout to avoid stampedes of several workers that are booted at the same time
        max_flush_time = self._max_flush_time * random.uniform(0.9, 1.1) if self._max_flush_time else None

        while True:
            since_last_flush = timeit.default_timer() - self._last_flush
            # take max flush time into account to calculate timeout
            timeout = max(0, max_flush_time - since_last_flush) if max_flush_time else None
            timed_out = False
            try:
                event_type, data, flush = self._event_queue.get(block=True, timeout=timeout)
            except compat.queue.Empty:
                event_type, data, flush = None, None, None
                timed_out = True

            if event_type == "close":
                if buffer_written:
                    try:
                        self._flush(buffer)
                    except Exception as exc:
                        logger.error(
                            "Exception occurred while flushing the buffer "
                            "before closing the transport connection: {0}".format(exc)
                        )
                self._flushed.set()
                return  # time to go home!

            if data is not None:
                data = self._process_event(event_type, data)
                if data is not None:
                    buffer.write((self._json_serializer({event_type: data}) + "\n").encode("utf-8"))
                    buffer_written = True
                    self._counts[event_type] += 1

            queue_size = 0 if buffer.fileobj is None else buffer.fileobj.tell()

            if flush:
                logger.debug("forced flush")
            elif timed_out or timeout == 0:
                # update last flush time, as we might have waited for a non trivial amount of time in
                # _event_queue.get()
                since_last_flush = timeit.default_timer() - self._last_flush
                logger.debug(
                    "flushing due to time since last flush %.3fs > max_flush_time %.3fs",
                    since_last_flush,
                    max_flush_time,
                )
                flush = True
            elif self._max_buffer_size and queue_size > self._max_buffer_size:
                logger.debug(
                    "flushing since queue size %d bytes > max_queue_size %d bytes", queue_size, self._max_buffer_size
                )
                flush = True
            if flush:
                if buffer_written:
                    self._flush(buffer)
                self._last_flush = timeit.default_timer()
                buffer = self._init_buffer()
                buffer_written = False
                max_flush_time = self._max_flush_time * random.uniform(0.9, 1.1) if self._max_flush_time else None
                self._flushed.set()

    def _process_event(self, event_type, data):
        # Run the data through processors
        for processor in self._processors:
            if not hasattr(processor, "event_types") or event_type in processor.event_types:
                try:
                    data = processor(self.client, data)
                    if not data:
                        logger.debug(
                            "Dropped event of type %s due to processor %s.%s",
                            event_type,
                            processor.__module__,
                            processor.__name__,
                        )
                        return None
                except Exception:
                    logger.warning(
                        "Dropped event of type %s due to exception in processor %s.%s",
                        event_type,
                        processor.__module__,
                        processor.__name__,
                        exc_info=True,
                    )
                    return None
        return data

    def _init_buffer(self):
        buffer = gzip.GzipFile(fileobj=compat.BytesIO(), mode="w", compresslevel=self._compress_level)
        data = (self._json_serializer({"metadata": self._metadata}) + "\n").encode("utf-8")
        buffer.write(data)
        return buffer

    def _init_event_queue(self, chill_until, max_chill_time):
        # some libraries like eventlet monkeypatch queue.Queue and switch out the implementation.
        # In those cases we can't rely on internals of queue.Queue to be there, so we simply use
        # their queue and forgo the optimizations of ChilledQueue. In the case of eventlet, this
        # isn't really a loss, because the main reason for ChilledQueue (avoiding context switches
        # due to the event processor thread being woken up all the time) is not an issue.
        if all(
            (
                hasattr(compat.queue.Queue, "not_full"),
                hasattr(compat.queue.Queue, "not_empty"),
                hasattr(compat.queue.Queue, "unfinished_tasks"),
            )
        ):
            return ChilledQueue(maxsize=10000, chill_until=chill_until, max_chill_time=max_chill_time)
        else:
            return compat.queue.Queue(maxsize=10000)

    def _flush(self, buffer):
        """
        Flush the queue. This method should only be called from the event processing queue
        :return: None
        """
        if not self.state.should_try():
            logger.error("dropping flushed data due to transport failure back-off")
        else:
            fileobj = buffer.fileobj  # get a reference to the fileobj before closing the gzip file
            buffer.close()

            # StringIO on Python 2 does not have getbuffer, so we need to fall back to getvalue
            data = fileobj.getbuffer() if hasattr(fileobj, "getbuffer") else fileobj.getvalue()
            try:
                self.send(data)
                self.handle_transport_success()
            except Exception as e:
                self.handle_transport_fail(e)

    def start_thread(self, pid=None):
        super(Transport, self).start_thread(pid=pid)
        if (not self._thread or self.pid != self._thread.pid) and not self._closed:
            try:
                self._thread = threading.Thread(target=self._process_queue, name="eapm event processor thread")
                self._thread.daemon = True
                self._thread.pid = self.pid
                self._thread.start()
            except RuntimeError:
                pass

    def send(self, data):
        """
        You need to override this to do something with the actual
        data. Usually - this is sending to a server
        """
        raise NotImplementedError

    def close(self):
        """
        Cleans up resources and closes connection
        :return:
        """
        if self._closed or (not self._thread or self._thread.pid != os.getpid()):
            return
        self._closed = True
        self.queue("close", None)
        if not self._flushed.wait(timeout=self._max_flush_time):
            logger.error("Closing the transport connection timed out.")

    stop_thread = close

    def flush(self):
        """
        Trigger a flush of the queue.
        Note: this method will only return once the queue is empty. This means it can block indefinitely if more events
        are produced in other threads than can be consumed.
        """
        self.queue(None, None, flush=True)
        if not self._flushed.wait(timeout=self._max_flush_time):
            raise ValueError("flush timed out")

    def handle_transport_success(self, **kwargs):
        """
        Success handler called by the transport on successful send
        """
        self.state.set_success()

    def handle_transport_fail(self, exception=None, **kwargs):
        """
        Failure handler called by the transport on send failure
        """
        message = str(exception)
        logger.error("Failed to submit message: %r", message, exc_info=getattr(exception, "print_trace", True))
        self.state.set_fail()


# left for backwards compatibility
AsyncTransport = Transport


class TransportState(object):
    ONLINE = 1
    ERROR = 0

    def __init__(self):
        self.status = self.ONLINE
        self.last_check = None
        self.retry_number = -1

    def should_try(self):
        if self.status == self.ONLINE:
            return True

        interval = min(self.retry_number, 6) ** 2

        return timeit.default_timer() - self.last_check > interval

    def set_fail(self):
        self.status = self.ERROR
        self.retry_number += 1
        self.last_check = timeit.default_timer()

    def set_success(self):
        self.status = self.ONLINE
        self.last_check = None
        self.retry_number = -1

    def did_fail(self):
        return self.status == self.ERROR


class ChilledQueue(compat.queue.Queue, object):
    """
    A queue subclass that is a bit more chill about how often it notifies the not empty event

    Note: we inherit from object because queue.Queue is an old-style class in Python 2. This can
    be removed once we stop support for Python 2
    """

    def __init__(self, maxsize=0, chill_until=100, max_chill_time=1.0):
        self._chill_until = chill_until
        self._max_chill_time = max_chill_time
        self._last_unchill = time.time()
        super(ChilledQueue, self).__init__(maxsize=maxsize)

    def put(self, item, block=True, timeout=None, chill=True):
        """Put an item into the queue.

        If optional args 'block' is true and 'timeout' is None (the default),
        block if necessary until a free slot is available. If 'timeout' is
        a non-negative number, it blocks at most 'timeout' seconds and raises
        the Full exception if no free slot was available within that time.
        Otherwise ('block' is false), put an item on the queue if a free slot
        is immediately available, else raise the Full exception ('timeout'
        is ignored in that case).
        """
        with self.not_full:
            if self.maxsize > 0:
                if not block:
                    if self._qsize() >= self.maxsize:
                        raise compat.queue.Full
                elif timeout is None:
                    while self._qsize() >= self.maxsize:
                        self.not_full.wait()
                elif timeout < 0:
                    raise ValueError("'timeout' must be a non-negative number")
                else:
                    endtime = time.time() + timeout
                    while self._qsize() >= self.maxsize:
                        remaining = endtime - time.time()
                        if remaining <= 0.0:
                            raise compat.queue.Full
                        self.not_full.wait(remaining)
            self._put(item)
            self.unfinished_tasks += 1
            if (
                not chill
                or self._qsize() > self._chill_until
                or (time.time() - self._last_unchill) > self._max_chill_time
            ):
                self.not_empty.notify()
                self._last_unchill = time.time()
