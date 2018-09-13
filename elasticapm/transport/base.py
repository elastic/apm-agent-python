# -*- coding: utf-8 -*-
import gzip
import logging
import threading
import time

from elasticapm.utils import json_encoder
from elasticapm.utils.compat import BytesIO

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
        success_callback=None,
        failure_callback=None,
        **kwargs
    ):
        """
        Create a new Transport instance

        :param metadata: Metadata object to prepend to every queue
        :param compress_level: GZip compress level. If zero, no GZip compression will be used
        :param json_serializer: serializer to use for JSON encoding
        :param max_flush_time: Maximum time between flushes in seconds
        :param max_buffer_size: Maximum size of buffer before flush
        :param success_callback: function to call after successful flush
        :param failure_callback: function to call after failed flush
        :param kwargs:
        """
        self._metadata = metadata if metadata is not None else {}
        self._compress_level = compress_level
        self._json_serializer = json_serializer
        self._max_flush_time = max_flush_time
        self._max_buffer_size = max_buffer_size
        self._success_callback = success_callback
        self._failure_callback = failure_callback
        self._queued_data = None
        self._flush_lock = threading.Lock()
        self._last_flush = time.time()

    def queue(self, event_type, data, flush=False):
        self._queue(self.queued_data, (self._json_serializer({event_type: data}) + "\n").encode("utf-8"))
        since_last_flush = time.time() - self._last_flush
        queue_size = self.queued_data_size
        if flush:
            logger.debug("forced flush")
            self.flush()
        elif self._max_flush_time and since_last_flush > self._max_flush_time:
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

    def _queue(self, queue, data):
        queue.write((self._json_serializer(data) + "\n").encode("utf-8"))

    @property
    def queued_data(self):
        if self._queued_data is None:
            if self._compress_level:
                self._queued_data = gzip.GzipFile(fileobj=BytesIO(), mode="w", compresslevel=self._compress_level)
            else:
                self._queued_data = BytesIO()
            self._queue(self.queued_data, {"metadata": self._metadata})
        return self._queued_data

    @property
    def queued_data_size(self):
        f = self.queued_data
        # return size of the underlying BytesIO object if it is compressed
        return f.fileobj.tell() if hasattr(f, "fileobj") else f.tell()

    def flush(self, sync=False):
        with self._flush_lock:
            queued_data, self._queued_data = self._queued_data, None
            if queued_data:
                if self._compress_level:
                    fileobj = queued_data.fileobj  # get a reference to the fileobj before closing the gzip file
                    queued_data.close()
                else:
                    fileobj = queued_data
                # StringIO on Python 2 does not have getbuffer, so we need to fall back to getvalue
                data = fileobj.getbuffer() if hasattr(fileobj, "getbuffer") else fileobj.getvalue()
                if hasattr(self, "send_async") and not sync:
                    self.send_async(data)
                else:
                    self.send(data)
            self._last_flush = time.time()

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
        self.flush(sync=True)


class AsyncTransport(Transport):
    async_mode = True

    def send_async(self, data, success_callback=None, fail_callback=None):
        raise NotImplementedError
