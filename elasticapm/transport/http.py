# -*- coding: utf-8 -*-
import logging
import os
import socket
import ssl
import sys

import certifi
import urllib3
from urllib3.connection import HTTPConnection
from urllib3.exceptions import MaxRetryError, TimeoutError

from elasticapm.transport.base import TransportException
from elasticapm.transport.http_base import AsyncHTTPTransportBase, HTTPTransportBase
from elasticapm.utils import compat

logger = logging.getLogger("elasticapm.transport.http")


class Transport(HTTPTransportBase):
    def __init__(self, url, **kwargs):
        super(Transport, self).__init__(url, **kwargs)
        pool_kwargs = {"cert_reqs": "CERT_REQUIRED", "ca_certs": certifi.where(), "block": True}
        if not self._verify_server_cert:
            pool_kwargs["cert_reqs"] = ssl.CERT_NONE
            pool_kwargs["assert_hostname"] = False
        proxy_url = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY"))
        if sys.platform.startswith("linux"):
            pool_kwargs["socket_options"] = HTTPConnection.default_socket_options + [
                (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
                (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 1),
                (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3),
                (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3),
            ]
        elif sys.platform == "darwin":
            TCP_KEEPALIVE = 0x10
            pool_kwargs["socket_options"] = HTTPConnection.default_socket_options + [
                (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
                (socket.IPPROTO_TCP, TCP_KEEPALIVE, 3),
            ]
        # TODO: Windows, BSDs?
        if proxy_url:
            self.http = urllib3.ProxyManager(proxy_url, **pool_kwargs)
        else:
            self.http = urllib3.PoolManager(**pool_kwargs)

    def send(self, data):
        response = None

        if compat.PY2 and isinstance(self._url, compat.text_type):
            url = self._url.encode("utf-8")
        else:
            url = self._url
        try:
            try:
                response = self.http.urlopen(
                    "POST", url, body=data, headers=self._headers, timeout=self._timeout, preload_content=False
                )
                logger.info("Sent request, url=%s size=%.2fkb status=%s", url, len(data) / 1024.0, response.status)
            except Exception as e:
                print_trace = True
                if isinstance(e, MaxRetryError) and isinstance(e.reason, TimeoutError):
                    message = "Connection to APM Server timed out " "(url: %s, timeout: %s seconds)" % (
                        self._url,
                        self._timeout,
                    )
                    print_trace = False
                else:
                    message = "Unable to reach APM Server: %s (url: %s)" % (e, self._url)
                raise TransportException(message, data, print_trace=print_trace)
            body = response.read()
            if response.status >= 400:
                if response.status == 429:  # rate-limited
                    message = "Temporarily rate limited: "
                    print_trace = False
                else:
                    message = "HTTP %s: " % response.status
                    print_trace = True
                message += body.decode("utf8", errors="replace")
                raise TransportException(message, data, print_trace=print_trace)
            return response.getheader("Location")
        finally:
            if response:
                response.close()


class AsyncTransport(AsyncHTTPTransportBase, Transport):
    async_mode = True
    sync_transport = Transport
