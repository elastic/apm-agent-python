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
import json
import re
import ssl
import urllib.parse
from urllib.request import getproxies_environment, proxy_bypass_environment

import urllib3
from urllib3.exceptions import MaxRetryError, TimeoutError

from elasticapm.transport.exceptions import TransportException
from elasticapm.transport.http_base import HTTPTransportBase
from elasticapm.utils import json_encoder, read_pem_file
from elasticapm.utils.logging import get_logger

try:
    import certifi
except ImportError:
    certifi = None

logger = get_logger("elasticapm.transport.http")


class Transport(HTTPTransportBase):
    def __init__(self, url: str, *args, **kwargs) -> None:
        super(Transport, self).__init__(url, *args, **kwargs)
        pool_kwargs = {"cert_reqs": "CERT_REQUIRED", "ca_certs": self.ca_certs, "block": True}
        if url.startswith("https"):
            if self._server_cert:
                pool_kwargs.update(
                    {"assert_fingerprint": self.cert_fingerprint, "assert_hostname": False, "cert_reqs": ssl.CERT_NONE}
                )
                del pool_kwargs["ca_certs"]
            elif not self._verify_server_cert:
                pool_kwargs["cert_reqs"] = ssl.CERT_NONE
                pool_kwargs["assert_hostname"] = False
        self._pool_kwargs = pool_kwargs
        self._http = None
        self._url = url

    def send(self, data, forced_flush=False):
        response = None

        headers = self._headers.copy() if self._headers else {}
        headers.update(self.auth_headers)
        headers.update(
            {
                b"Content-Type": b"application/x-ndjson",
                b"Content-Encoding": b"gzip",
            }
        )

        url = self._url
        if forced_flush:
            url = f"{url}?flushed=true"
        try:
            try:
                response = self.http.urlopen(
                    "POST", url, body=data, headers=headers, timeout=self._timeout, preload_content=False
                )
                logger.debug("Sent request, url=%s size=%.2fkb status=%s", url, len(data) / 1024.0, response.status)
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
                message += body.decode("utf8", errors="replace")[:10000]
                raise TransportException(message, data, print_trace=print_trace)
            return response.getheader("Location")
        finally:
            if response:
                response.close()

    @property
    def http(self) -> urllib3.PoolManager:
        if not self._http:
            url_parts = urllib.parse.urlparse(self._url)
            proxies = getproxies_environment()
            proxy_url = proxies.get("https", proxies.get("http", None))
            if proxy_url and not proxy_bypass_environment(url_parts.netloc):
                self._http = urllib3.ProxyManager(proxy_url, **self._pool_kwargs)
            else:
                self._http = urllib3.PoolManager(**self._pool_kwargs)
        return self._http

    def handle_fork(self) -> None:
        # reset http pool to avoid sharing connections with the parent process
        self._http = None

    def get_config(self, current_version=None, keys=None):
        """
        Gets configuration from a remote APM Server

        :param current_version: version of the current configuration
        :param keys: a JSON-serializable dict to identify this instance, e.g.
                {
                    "service": {
                        "name": "foo",
                        "environment": "bar"
                    }
                }
        :return: a three-tuple of new version, config dictionary and validity in seconds.
                 Any element of the tuple can be None.
        """
        url = self._config_url
        data = json_encoder.dumps(keys).encode("utf-8")
        headers = self._headers.copy()
        headers[b"Content-Type"] = "application/json"
        headers.update(self.auth_headers)
        max_age = 300
        if current_version:
            headers["If-None-Match"] = current_version
        try:
            response = self.http.urlopen(
                "POST", url, body=data, headers=headers, timeout=self._timeout, preload_content=False
            )
        except (urllib3.exceptions.RequestError, urllib3.exceptions.HTTPError) as e:
            logger.debug("HTTP error while fetching remote config: %s", str(e))
            return current_version, None, max_age
        body = response.read()

        max_age = self._get_cache_control_max_age(response.headers) or max_age

        if response.status == 304:
            # config is unchanged, return
            logger.debug("Configuration unchanged")
            return current_version, None, max_age
        elif response.status >= 400:
            return None, None, max_age

        if not body:
            logger.debug("APM Server answered with empty body and status code %s", response.status)
            return current_version, None, max_age
        body = body.decode("utf-8")
        try:
            data = json_encoder.loads(body)
            return response.headers.get("Etag"), data, max_age
        except json.JSONDecodeError:
            logger.warning("Failed decoding APM Server response as JSON: %s", body)
            return current_version, None, max_age

    def _get_cache_control_max_age(self, response_headers):
        max_age = None
        if "Cache-Control" in response_headers:
            try:
                cc_max_age = int(next(re.finditer(r"max-age=(\d+)", response_headers["Cache-Control"])).groups()[0])
                if cc_max_age <= 0:
                    # max_age remains at default value
                    pass
                elif cc_max_age < 5:
                    max_age = 5
                else:
                    max_age = cc_max_age
            except StopIteration:
                logger.debug("Could not parse Cache-Control header: %s", response_headers["Cache-Control"])
        return max_age

    def _process_queue(self):
        if not self.client.server_version:
            self.fetch_server_info()
        super()._process_queue()

    def fetch_server_info(self):
        headers = self._headers.copy() if self._headers else {}
        headers.update(self.auth_headers)
        headers[b"accept"] = b"text/plain"
        try:
            response = self.http.urlopen("GET", self._server_info_url, headers=headers, timeout=self._timeout)
            body = response.data
            data = json_encoder.loads(body.decode("utf8"))
            version = data["version"]
            logger.debug("Fetched APM Server version %s", version)
            self.client.server_version = version_string_to_tuple(version)
        except (urllib3.exceptions.RequestError, urllib3.exceptions.HTTPError) as e:
            logger.debug("HTTP error while fetching server information: %s", str(e))
        except json.JSONDecodeError as e:
            logger.debug(
                f"JSON decoding error while fetching server information. Error: {str(e)} Body: {body.decode('utf8')}"
            )
        except (KeyError, TypeError):
            logger.debug("No version key found in server response: %s", response.data)

    @property
    def cert_fingerprint(self):
        if self._server_cert:
            with open(self._server_cert, "rb") as f:
                cert_data = read_pem_file(f)
            digest = hashlib.sha256()
            digest.update(cert_data)
            return digest.hexdigest()
        return None

    @property
    def auth_headers(self):
        headers = super(Transport, self).auth_headers
        return {k.encode("ascii"): v.encode("ascii") for k, v in headers.items()}

    @property
    def ca_certs(self):
        """
        Return location of certificate store. If it is available and not disabled via setting,
        this will return the location of the certifi certificate store.
        """
        return certifi.where() if (certifi and self.client.config.use_certifi) else None


def version_string_to_tuple(version):
    if version:
        version_parts = re.split(r"[.\-]", version)
        return tuple(int(p) if p.isdigit() else p for p in version_parts)
    return ()


# left for backwards compatibility
AsyncTransport = Transport
