# -*- coding: utf-8 -*-
import gzip
import threading
import time

from elasticapm.utils import json_encoder
from elasticapm.utils.compat import BytesIO


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
        success_callback=None,
        failure_callback=None,
        **kwargs
    ):
        self._metadata = metadata if metadata is not None else {}
        self._compress_level = compress_level
        self._json_serializer = json_serializer
        self._success_callback = success_callback
        self._failure_callback = failure_callback
        self._queued_data = None
        self._flush_lock = threading.Lock()
        self._last_flush = time.time()

    def queue(self, event_type, data, flush=False):
        self.queued_data.write((self._json_serializer({event_type: data}) + "\n").encode("utf-8"))
        if flush or (time.time() - self._last_flush) > 10:
            self.flush()

    @property
    def queued_data(self):
        if self._queued_data is None:
            self._queued_data = gzip.GzipFile(fileobj=BytesIO(), mode="w", compresslevel=self._compress_level)
            self.queue("metadata", self._metadata)
        return self._queued_data

    @property
    def queued_data_size(self):
        return self.queued_data.tell()

    def flush(self, sync=False):
        with self._flush_lock:
            queued_data, self._queued_data = self._queued_data, None
            if queued_data:
                fileobj = queued_data.fileobj  # get a reference to the fileobj before closing the gzip file
                queued_data.close()
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
