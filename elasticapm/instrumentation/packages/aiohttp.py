from elasticapm import async_capture_span
from elasticapm.instrumentation.packages.asyncio_base import \
    AsyncAbstractInstrumentedModule
from elasticapm.utils import default_ports
from elasticapm.utils.compat import urlparse


def get_host_from_url(url):
    parsed_url = urlparse.urlparse(url)
    host = parsed_url.hostname or " "

    if (
        parsed_url.port and
        default_ports.get(parsed_url.scheme) != parsed_url.port
    ):
        host += ":" + str(parsed_url.port)

    return host


class AioHttpClientInstrumentation(AsyncAbstractInstrumentedModule):
    name = 'aiohttp_client'

    instrument_list = [
        ("aiohttp.client", "ClientSession._request"),
    ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        method = kwargs['method'] if 'method' in kwargs else args[0]
        url = kwargs['method'] if 'method' in kwargs else args[1]

        signature = " ".join([method.upper(), get_host_from_url(url)])

        async with async_capture_span(signature, "ext.http.aiohttp", {'url': url}, leaf=True):
            return await wrapped(*args, **kwargs)
