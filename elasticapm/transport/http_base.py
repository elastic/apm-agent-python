# -*- coding: utf-8 -*-
from elasticapm.transport.base import AsyncTransport, Transport
from elasticapm.utils import compat


class HTTPTransportBase(Transport):
    def __init__(
        self, url, verify_server_cert=True, compress_level=5, metadata=None, headers=None, timeout=None, **kwargs
    ):
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
        super(HTTPTransportBase, self).__init__(metadata=metadata, compress_level=compress_level, **kwargs)

    def send(self, data):
        """
        Sends a request to a remote webserver using HTTP POST.

        Returns the shortcut URL of the recorded error on Elastic APM
        """
        raise NotImplementedError()


class AsyncHTTPTransportBase(AsyncTransport, HTTPTransportBase):
    async_mode = True
    sync_transport = HTTPTransportBase
