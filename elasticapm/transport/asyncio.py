import asyncio

import aiohttp

from .base import TransportException
from .http_base import HTTPTransportBase


class AsyncioHTTPTransport(HTTPTransportBase):
    """
    HTTP Transport ready for asyncio
    """

    async_mode = False
    binary_headers = False

    def __init__(self, url, **kwargs):
        super(AsyncioHTTPTransport, self).__init__(url, **kwargs)
        self._client = None

    def send(self, data):
        loop = asyncio.get_event_loop()
        task = loop.create_task(self._send(data))
        task.add_done_callback(self.handle_transport_response)

    async def _send(self, data):
        try:
            response = await self.client.post(self._url, data=data, headers=self._headers, timeout=self._timeout)
            assert response.status == 202
        except asyncio.TimeoutError as e:
            print_trace = True
            message = "Connection to APM Server timed out " "(url: %s, timeout: %s seconds)" % (
                self._url,
                self._timeout,
            )
            raise TransportException(message, data, print_trace=print_trace) from e
        except AssertionError as e:
            print_trace = True
            body = await response.read()
            if response.status == 429:
                message = "Temporarily rate limited: "
                print_trace = False
            else:
                message = "Unable to reach APM Server: "
            message += "HTTP %s: (url: %s, body: %s)" % (response.status, self._url, body)
            raise TransportException(message, data, print_trace=print_trace) from e
        except Exception as e:
            print_trace = True
            message = "Unable to reach APM Server: %s (url: %s)" % (e, self._url)
            raise TransportException(message, data, print_trace=print_trace) from e
        else:
            return response.headers.get("Location")

    def handle_transport_response(self, task):
        try:
            task.result()
            self.handle_transport_success()
        except Exception as exc:
            self.handle_transport_fail(exception=exc)

    @property
    def client(self):
        if not self._client:
            loop = asyncio.get_event_loop()
            session_kwargs = {"loop": loop}
            if not self._verify_server_cert:
                session_kwargs["connector"] = aiohttp.TCPConnector(verify_ssl=False)
            self._client = aiohttp.ClientSession(**session_kwargs)
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
