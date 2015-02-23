# -*- coding: utf-8 -*-
import logging
import time
import threading

try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen

from opbeat.conf import defaults
from opbeat.contrib.async import AsyncWorker
from opbeat.transport.base import Transport, AsyncTransport

logger = logging.getLogger('opbeat')


class HTTPTransport(Transport):

    scheme = ['http', 'https']

    def __init__(self, parsed_url):
        self.check_scheme(parsed_url)

        self._parsed_url = parsed_url
        self._url = parsed_url.geturl()

    def send(self, data, headers, timeout=None):
        """
        Sends a request to a remote webserver using HTTP POST.
        """
        req = Request(self._url, headers=headers)
        if timeout is None:
            timeout = defaults.TIMEOUT
        try:
            response = urlopen(req, data, timeout).read()
        except TypeError:
            response = urlopen(req, data).read()
        return response


class AsyncHTTPTransport(AsyncTransport, HTTPTransport):
    scheme = ['http', 'https']
    async = True
    _worker = None

    def __init__(self, parsed_url):
        super(AsyncHTTPTransport, self).__init__(parsed_url)
        if self._url.startswith('async+'):
            self._url = self._url[6:]

    @property
    def worker(self):
        if not self._worker:
            self._worker = AsyncWorker()
        return self._worker

    def send_sync(self, data=None, headers=None, success_callback=None, fail_callback=None):
        try:
            HTTPTransport.send(self, data, headers)
            if callable(success_callback):
                success_callback()
        except Exception:
            if callable(fail_callback):
                fail_callback()

    def send_async(self, data, headers, success_callback=None, fail_callback=None):
        kwargs = {
            'data': data,
            'headers': headers,
            'success_callback': success_callback,
            'fail_callback': fail_callback,
        }
        self.worker.queue(self.send_sync, kwargs)
