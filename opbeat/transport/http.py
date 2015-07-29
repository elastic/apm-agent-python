# -*- coding: utf-8 -*-
import logging
import socket
import sys

try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen

from opbeat.conf import defaults
from opbeat.contrib.async_worker import AsyncWorker
from opbeat.transport.base import Transport, AsyncTransport, TransportException
from opbeat.utils import six
from opbeat.utils.compat import HTTPError

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
            try:
                response = urlopen(req, data, timeout)
            except TypeError:
                response = urlopen(req, data)
        except Exception as e:
            if isinstance(e, socket.timeout):
                message = (
                    "Connection to Opbeat server timed out "
                    "(url: %s, timeout: %d seconds)" % (self._url, timeout)
                )
            elif isinstance(e, HTTPError):
                body = e.read()
                message = (
                    'Unable to reach Opbeat server: '
                    '%s (url: %s, body: %s)' % (e, self._url, body)
                )
            else:
                message = 'Unable to reach Opbeat server: %s (url: %s)' % (
                    e, self._url
                )
            raise TransportException(message, data)
        return response


class AsyncHTTPTransport(AsyncTransport, HTTPTransport):
    scheme = ['http', 'https']
    async_mode = True

    def __init__(self, parsed_url):
        super(AsyncHTTPTransport, self).__init__(parsed_url)
        if self._url.startswith('async+'):
            self._url = self._url[6:]
        self._worker = None

    @property
    def worker(self):
        if not self._worker or not self._worker.is_alive():
            self._worker = AsyncWorker()
        return self._worker

    def send_sync(self, data=None, headers=None, success_callback=None,
                  fail_callback=None):
        try:
            response = HTTPTransport.send(self, data, headers)
            if callable(success_callback):
                success_callback(url=response.info().get('Location'))
        except Exception as e:
            if callable(fail_callback):
                fail_callback(exception=e)

    def send_async(self, data, headers, success_callback=None,
                   fail_callback=None):
        kwargs = {
            'data': data,
            'headers': headers,
            'success_callback': success_callback,
            'fail_callback': fail_callback,
        }
        self.worker.queue(self.send_sync, kwargs)

    def close(self):
        if self._worker:
            self._worker.main_thread_terminated()
