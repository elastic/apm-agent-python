# -*- coding: utf-8 -*-
from elasticapm.contrib.async_worker import AsyncWorker
from elasticapm.transport.base import AsyncTransport, Transport


class HTTPTransportBase(Transport):
    scheme = ["http", "https"]

    def __init__(self, parsed_url, verify_server_cert=True):
        self.check_scheme(parsed_url)

        self._parsed_url = parsed_url
        self._url = parsed_url.geturl()
        self._verify_server_cert = verify_server_cert

    def send(self, data, headers, timeout=None):
        """
        Sends a request to a remote webserver using HTTP POST.

        Returns the shortcut URL of the recorded error on Elastic APM
        """
        raise NotImplementedError()


class AsyncHTTPTransportBase(AsyncTransport, HTTPTransportBase):
    scheme = ["http", "https"]
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

    def send_sync(self, data=None, headers=None, success_callback=None, fail_callback=None):
        try:
            url = self.sync_transport.send(self, data, headers)
            if callable(success_callback):
                success_callback(url=url)
        except Exception as e:
            if callable(fail_callback):
                fail_callback(exception=e)

    def send_async(self, data, headers, success_callback=None, fail_callback=None):
        kwargs = {
            "data": data,
            "headers": headers,
            "success_callback": success_callback,
            "fail_callback": fail_callback,
        }
        self.worker.queue(self.send_sync, kwargs)

    def close(self):
        if self._worker:
            self._worker.main_thread_terminated()
