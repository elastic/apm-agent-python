# -*- coding: utf-8 -*-
import gzip
import logging
import threading
import timeit
from collections import defaultdict

from elasticapm.contrib.async_worker import AsyncWorker
from elasticapm.utils import compat, json_encoder

logger = logging.getLogger("elasticapm.transport")


class TransportException(Exception):
    def __init__(self, message, data=None, print_trace=True):
        super(TransportException, self).__init__(message)
        self.data = data
        self.print_trace = print_trace


class Transport(object):
    """
    All transport implementations need to subclass this class

    You must implement a send method..
    """

    async_mode = False

    def __init__(
        self,
        metadata=None,
        compress_level=5,
        json_serializer=json_encoder.dumps,
        max_flush_time=None,
        max_buffer_size=None,
        **kwargs
    ):
        """
        Create a new Transport instance

        :param metadata: Metadata object to prepend to every queue
        :param compress_level: GZip compress level. If zero, no GZip compression will be used
        :param json_serializer: serializer to use for JSON encoding
        :param max_flush_time: Maximum time between flushes in seconds
        :param max_buffer_size: Maximum size of buffer before flush
        :param kwargs:
        """
        self.state = TransportState()
        self._metadata = metadata if metadata is not None else {}
        self._compress_level = min(9, max(0, compress_level if compress_level is not None else 0))
        self._json_serializer = json_serializer
        self._max_flush_time = max_flush_time
        self._max_buffer_size = max_buffer_size
        self._queued_data = None
        self._event_queue = compat.queue.Queue(maxsize=100)
        self._event_process_thread = threading.Thread(
            target=self._process_queue, name="eapm event processor", daemon=True
        )
        self._last_flush = timeit.default_timer()
        self._counts = defaultdict(int)
        self._closed = False

    def queue(self, event_type, data, flush=False):
        if not self._event_process_thread.is_alive() and not self._closed:
            self._event_process_thread.start()
        try:
            self._event_queue.put_nowait((event_type, data, flush))
        except compat.queue.Full:
            logger.warning("Event of type %s dropped due to full event queue", event_type)

    def _process_queue(self):
        while True:
            since_last_flush = timeit.default_timer() - self._last_flush
            # take max flush time into account to calculate timeout
            timeout = max(0, self._max_flush_time - since_last_flush) if self._max_flush_time else None
            timed_out = False
            try:
                event_type, data, flush = self._event_queue.get(block=True, timeout=timeout)
            except compat.queue.Empty:
                event_type, data, flush = None, None, None
                timed_out = True

            if event_type == "close":
                self.flush(sync=True)
                return  # time to go home!

            queued_data = self.queued_data
            if data is not None:
                queued_data.write((self._json_serializer({event_type: data}) + "\n").encode("utf-8"))
                self._counts[event_type] += 1

            queue_size = 0 if queued_data.fileobj is None else queued_data.fileobj.tell()

            if flush:
                logger.debug("forced flush")
                self.flush()
            elif timed_out or timeout == 0:
                logger.debug(
                    "flushing due to time since last flush %.3fs > max_flush_time %.3fs",
                    since_last_flush,
                    self._max_flush_time,
                )
                self.flush()
            elif self._max_buffer_size and queue_size > self._max_buffer_size:
                logger.debug(
                    "flushing since queue size %d bytes > max_queue_size %d bytes", queue_size, self._max_buffer_size
                )
                self.flush()

    @property
    def queued_data(self):
        if self._queued_data is None:
            self._queued_data = gzip.GzipFile(fileobj=compat.BytesIO(), mode="w", compresslevel=self._compress_level)
            data = (self._json_serializer({"metadata": self._metadata}) + "\n").encode("utf-8")
            self._queued_data.write(data)
        return self._queued_data

    def flush(self, sync=False):
        """
        Flush the queue
        :param sync: if true, flushes the queue synchronously in the current thread
        :return: None
        """
        queued_data, self._queued_data = self._queued_data, None
        if queued_data and not self.state.should_try():
            logger.error("dropping flushed data due to transport failure back-off")
        elif queued_data:
            fileobj = queued_data.fileobj  # get a reference to the fileobj before closing the gzip file
            queued_data.close()

            # StringIO on Python 2 does not have getbuffer, so we need to fall back to getvalue
            data = fileobj.getbuffer() if hasattr(fileobj, "getbuffer") else fileobj.getvalue()
            if hasattr(self, "send_async") and not sync:
                self.send_async(data)
            else:
                try:
                    self.send(data)
                    self.handle_transport_success()
                except Exception as e:
                    self.handle_transport_fail(e)
        self._last_flush = timeit.default_timer()

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
        self._closed = True
        self.queue("close", None)
        if self._event_process_thread.is_alive():
            self._event_process_thread.join()

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


class AsyncTransport(Transport):
    async_mode = True
    sync_transport = Transport

    def __init__(self, *args, **kwargs):
        super(AsyncTransport, self).__init__(*args, **kwargs)
        self._worker = None

    @property
    def worker(self):
        if not self._worker or not self._worker.is_alive():
            self._worker = AsyncWorker()
        return self._worker

    def send_sync(self, data=None):
        try:
            self.sync_transport.send(self, data)
            self.handle_transport_success()
        except Exception as e:
            self.handle_transport_fail(exception=e)

    def send_async(self, data):
        self.worker.queue(self.send_sync, {"data": data})

    def close(self):
        super(AsyncTransport, self).close()
        if self._worker:
            self._worker.main_thread_terminated()


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
