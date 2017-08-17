import asyncio

import aiohttp

from elasticapm.conf import defaults

from .base import TransportException
from .http import HTTPTransport


class AsyncioHTTPTransport(HTTPTransport):
    """
    HTTP Transport ready for asyncio
    """

    def __init__(self, parsed_url):
        self.check_scheme(parsed_url)

        self._parsed_url = parsed_url
        self._url = parsed_url.geturl()
        loop = asyncio.get_event_loop()
        self.client = aiohttp.ClientSession(loop=loop)

    async def send(self, data, headers, timeout=None):
        """Use synchronous interface, because this is a coroutine."""

        if timeout is None:
            timeout = defaults.TIMEOUT
        try:
            with aiohttp.Timeout(timeout):
                async with self.client.post(self._url,
                                            data=data,
                                            headers=headers) as response:
                    assert response.status == 202
        except asyncio.TimeoutError as e:
            print_trace = True
            message = ("Connection to APM Server timed out "
                       "(url: %s, timeout: %d seconds)" % (self._url, timeout))
            raise TransportException(message, data,
                                     print_trace=print_trace) from e
        except AssertionError as e:
            print_trace = True
            body = await response.read()
            if response.status == 429:
                message = 'Temporarily rate limited: '
                print_trace = False
            else:
                message = 'Unable to reach APM Server: '
            message += '%s (url: %s, body: %s)' % (e, self._url, body)
            raise TransportException(message, data,
                                     print_trace=print_trace) from e
        except Exception as e:
            print_trace = True
            message = 'Unable to reach APM Server: %s (url: %s)' % (
                e, self._url)
            raise TransportException(message, data,
                                     print_trace=print_trace) from e
        else:
            return response.headers.get('Location')

    def __del__(self):
        self.client.close()
