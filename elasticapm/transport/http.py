# -*- coding: utf-8 -*-

#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import hashlib
import logging
import os
import ssl

import certifi
import urllib3
from urllib3.exceptions import MaxRetryError, TimeoutError

from elasticapm.transport.base import TransportException
from elasticapm.transport.http_base import AsyncHTTPTransportBase, HTTPTransportBase
from elasticapm.utils import compat, read_pem_file

logger = logging.getLogger("elasticapm.transport.http")


class Transport(HTTPTransportBase):
    def __init__(self, url, **kwargs):
        super(Transport, self).__init__(url, **kwargs)
        pool_kwargs = {"cert_reqs": "CERT_REQUIRED", "ca_certs": certifi.where(), "block": True}
        if self._server_cert:
            pool_kwargs.update(
                {"assert_fingerprint": self.cert_fingerprint, "assert_hostname": False, "cert_reqs": ssl.CERT_NONE}
            )
            del pool_kwargs["ca_certs"]
        elif not self._verify_server_cert:
            pool_kwargs["cert_reqs"] = ssl.CERT_NONE
            pool_kwargs["assert_hostname"] = False
        proxy_url = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY"))
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

    @property
    def cert_fingerprint(self):
        if self._server_cert:
            with open(self._server_cert, "rb") as f:
                cert_data = read_pem_file(f)
            digest = hashlib.sha256()
            digest.update(cert_data)
            return digest.hexdigest()
        return None


class AsyncTransport(AsyncHTTPTransportBase, Transport):
    async_mode = True
    sync_transport = Transport
