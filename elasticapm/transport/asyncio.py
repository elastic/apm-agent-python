import asyncio

import aiohttp
import async_timeout

from .base import TransportException
from .http_base import HTTPTransportBase


class AsyncioHTTPTransport(HTTPTransportBase):
    """
    HTTP Transport ready for asyncio
    """

    def __init__(self, parsed_url, **kwargs):
        super(AsyncioHTTPTransport, self).__init__(parsed_url, **kwargs)
        loop = asyncio.get_event_loop()
        session_kwargs = {"loop": loop}
        if not self._verify_server_cert:
            session_kwargs["connector"] = aiohttp.TCPConnector(verify_ssl=False)
        self.client = aiohttp.ClientSession(**session_kwargs)

    async def send(self, data, headers, timeout=None):
        """Use synchronous interface, because this is a coroutine."""

        try:
            with async_timeout.timeout(timeout):
                async with self.client.post(self._url, data=data, headers=headers) as response:
                    assert response.status == 202
        except asyncio.TimeoutError as e:
            print_trace = True
            message = "Connection to APM Server timed out " "(url: %s, timeout: %s seconds)" % (self._url, timeout)
            raise TransportException(message, data, print_trace=print_trace) from e
        except AssertionError as e:
            print_trace = True
            body = await response.read()
            if response.status == 429:
                message = "Temporarily rate limited: "
                print_trace = False
            else:
                message = "Unable to reach APM Server: "
            message += "%s (url: %s, body: %s)" % (e, self._url, body)
            raise TransportException(message, data, print_trace=print_trace) from e
        except Exception as e:
            print_trace = True
            message = "Unable to reach APM Server: %s (url: %s)" % (e, self._url)
            raise TransportException(message, data, print_trace=print_trace) from e
        else:
            return response.headers.get("Location")

    def __del__(self):
        self.client.close()
