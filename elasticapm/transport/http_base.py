# -*- coding: utf-8 -*-
from elasticapm.contrib.async_worker import AsyncWorker
from elasticapm.transport.base import AsyncTransport, Transport
from elasticapm.utils import compat


class HTTPTransportBase(Transport):
    def __init__(self, url, verify_server_cert=True, compress_level=5, metadata=None, headers=None, timeout=None):

        self._url = url
        self._verify_server_cert = verify_server_cert
        self._timeout = timeout
        self._headers = {
            k.encode("ascii")
            if isinstance(k, compat.text_type)
            else k: v.encode("ascii")
            if isinstance(v, compat.text_type)
            else v
            for k, v in (headers if headers is not None else {}).items()
        }
        super(HTTPTransportBase, self).__init__(metadata=metadata, compress_level=compress_level)

    def send(self, data):
        """
        Sends a request to a remote webserver using HTTP POST.

        Returns the shortcut URL of the recorded error on Elastic APM
        """
        raise NotImplementedError()


class AsyncHTTPTransportBase(AsyncTransport, HTTPTransportBase):
    async_mode = True
    sync_transport = HTTPTransportBase

    def __init__(self, parsed_url, **kwargs):
        super(AsyncHTTPTransportBase, self).__init__(parsed_url, **kwargs)
        if self._url.startswith("async+"):
            self._url = self._url[6:]
        self._worker = None

    @property
    def worker(self):
        if not self._worker or not self._worker.is_alive():
            self._worker = AsyncWorker()
        return self._worker

    def send_sync(self, data=None):
        try:
            url = self.sync_transport.send(self, data)
            if callable(self._success_callback):
                self._success_callback(url=url)
        except Exception as e:
            if callable(self._failure_callback):
                self._failure_callback(exception=e)

    def send_async(self, data, success_callback=None, fail_callback=None):
        self.worker.queue(self.send_sync, {"data": data})

    def close(self):
        super(AsyncHTTPTransportBase, self).close()
        if self._worker:
            self._worker.main_thread_terminated()
