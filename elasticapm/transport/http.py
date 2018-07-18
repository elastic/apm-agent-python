# -*- coding: utf-8 -*-
import logging
import os
import ssl

import certifi
import urllib3
from urllib3.exceptions import MaxRetryError, TimeoutError

from elasticapm.transport.base import TransportException
from elasticapm.transport.http_base import AsyncHTTPTransportBase, HTTPTransportBase
from elasticapm.utils import compat

logger = logging.getLogger("elasticapm.transport.http")


class Transport(HTTPTransportBase):

    scheme = ["http", "https"]

    def __init__(self, parsed_url, **kwargs):
        super(Transport, self).__init__(parsed_url, **kwargs)
        pool_kwargs = {"cert_reqs": "CERT_REQUIRED", "ca_certs": certifi.where(), "block": True}
        if not self._verify_server_cert:
            pool_kwargs["cert_reqs"] = ssl.CERT_NONE
            pool_kwargs["assert_hostname"] = False
        proxy_url = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY"))
        if proxy_url:
            self.http = urllib3.ProxyManager(proxy_url, **pool_kwargs)
        else:
            self.http = urllib3.PoolManager(**pool_kwargs)

    def send(self, data, headers, timeout=None):
        response = None

        # ensure headers are byte strings
        headers = {
            k.encode("ascii")
            if isinstance(k, compat.text_type)
            else k: v.encode("ascii")
            if isinstance(v, compat.text_type)
            else v
            for k, v in headers.items()
        }
        if compat.PY2 and isinstance(self._url, compat.text_type):
            url = self._url.encode("utf-8")
        else:
            url = self._url
        try:
            try:
                response = self.http.urlopen(
                    "POST", url, body=data, headers=headers, timeout=timeout, preload_content=False
                )
                logger.info("Sent request, url=%s size=%.2fkb status=%s", url, len(data) / 1024.0, response.status)
            except Exception as e:
                print_trace = True
                if isinstance(e, MaxRetryError) and isinstance(e.reason, TimeoutError):
                    message = "Connection to APM Server timed out " "(url: %s, timeout: %s seconds)" % (
                        self._url,
                        timeout,
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
                message += body.decode("utf8")
                raise TransportException(message, data, print_trace=print_trace)
            return response.getheader("Location")
        finally:
            if response:
                response.close()


class AsyncTransport(AsyncHTTPTransportBase, Transport):
    scheme = ["http", "https"]
    async_mode = True
    sync_transport = Transport
