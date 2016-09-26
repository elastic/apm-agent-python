# -*- coding: utf-8 -*-
import os

import certifi
import urllib3
from urllib3.exceptions import MaxRetryError, TimeoutError

from opbeat.conf import defaults
from opbeat.transport.base import TransportException
from opbeat.transport.http import AsyncHTTPTransport, HTTPTransport


class Urllib3Transport(HTTPTransport):

    scheme = ['http', 'https']

    def __init__(self, parsed_url):
        kwargs = {
            'cert_reqs': 'CERT_REQUIRED',
            'ca_certs': certifi.where(),
            'block': True,
        }
        proxy_url = os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
        if proxy_url:
            self.http = urllib3.ProxyManager(proxy_url, **kwargs)
        else:
            self.http = urllib3.PoolManager(**kwargs)
        super(Urllib3Transport, self).__init__(parsed_url)

    def send(self, data, headers, timeout=None):
        if timeout is None:
            timeout = defaults.TIMEOUT
        response = None
        try:
            try:
                response = self.http.urlopen(
                    'POST', self._url, body=data, headers=headers, timeout=timeout
                )
            except Exception as e:
                print_trace = True
                if isinstance(e, MaxRetryError) and isinstance(e.reason, TimeoutError):
                    message = (
                        "Connection to Opbeat server timed out "
                        "(url: %s, timeout: %d seconds)" % (self._url, timeout)
                    )
                    print_trace = False
                else:
                    message = 'Unable to reach Opbeat server: %s (url: %s)' % (
                        e, self._url
                    )
                raise TransportException(message, data, print_trace=print_trace)
            body = response.read()
            if response.status >= 400:
                if response.status == 429:  # rate-limited
                    message = 'Temporarily rate limited: '
                    print_trace = False
                else:
                    message = 'HTTP %s: ' % response.status
                    print_trace = True
                message += body.decode('utf8')
                raise TransportException(message, data, print_trace=print_trace)
            return response.getheader('Location')
        finally:
            if response:
                response.close()


class AsyncUrllib3Transport(AsyncHTTPTransport, Urllib3Transport):
    scheme = ['http', 'https']
    async_mode = True

    def send_sync(self, data=None, headers=None, success_callback=None,
                  fail_callback=None):
        try:
            url = Urllib3Transport.send(self, data, headers)
            if callable(success_callback):
                success_callback(url=url)
        except Exception as e:
            if callable(fail_callback):
                fail_callback(exception=e)
