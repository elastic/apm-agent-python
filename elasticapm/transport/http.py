# -*- coding: utf-8 -*-
import logging
import socket
import ssl

from elasticapm.conf import defaults
from elasticapm.contrib.async_worker import AsyncWorker
from elasticapm.transport.base import (AsyncTransport, Transport,
                                       TransportException)
from elasticapm.utils.compat import HTTPError

try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen


logger = logging.getLogger('elasticapm')


class HTTPTransport(Transport):

    scheme = ['http', 'https']

    def __init__(self, parsed_url, verify_certificate=True):
        self.check_scheme(parsed_url)

        self._parsed_url = parsed_url
        self._url = parsed_url.geturl()
        self._verify_certificate = verify_certificate
        if self._parsed_url.scheme == 'https' and hasattr(ssl, 'PROTOCOL_TLS'):  # not available before 2.7.9 / 3.4.3
            self._ssl_ctx = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS)
            if verify_certificate:
                self._ssl_ctx.verify_mode = ssl.CERT_REQUIRED
                self._ssl_ctx.check_hostname = True
            else:
                self._ssl_ctx.verify_mode = ssl.CERT_NONE
                self._ssl_ctx.check_hostname = False
        else:
            self._ssl_ctx = None

    def send(self, data, headers, timeout=None):
        """
        Sends a request to a remote webserver using HTTP POST.

        Returns the shortcut URL of the recorded error on Elastic APM
        """
        req = Request(self._url, headers=headers)
        urlopen_kwargs = {}
        if self._ssl_ctx:
            urlopen_kwargs['context'] = self._ssl_ctx
        if timeout is None:
            timeout = defaults.TIMEOUT
        response = None
        try:
            response = urlopen(req, data, timeout, **urlopen_kwargs)
        except Exception as e:
            print_trace = True
            if isinstance(e, socket.timeout):
                message = (
                    "Connection to APM Server timed out "
                    "(url: %s, timeout: %d seconds)" % (self._url, timeout)
                )
            elif isinstance(e, HTTPError):
                body = e.read()
                if e.code == 429:  # rate-limited
                    message = 'Temporarily rate limited: '
                    print_trace = False
                else:
                    message = 'Unable to reach APM Server: '
                message += '%s (url: %s, body: %s)' % (e, self._url, body)
            else:
                message = 'Unable to reach APM Server: %s (url: %s)' % (
                    e, self._url
                )
            raise TransportException(message, data, print_trace=print_trace)
        finally:
            if response:
                response.close()

        return response.info().get('Location')


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
            url = HTTPTransport.send(self, data, headers)
            if callable(success_callback):
                success_callback(url=url)
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
