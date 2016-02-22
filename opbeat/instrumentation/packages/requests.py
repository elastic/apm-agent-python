from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.traces import trace
from opbeat.utils import default_ports
from opbeat.utils.compat import urlparse


class RequestsInstrumentation(AbstractInstrumentedModule):
    name = 'requests'

    instrument_list = [
        ("requests.sessions", "Session.request"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if 'method' in kwargs:
            method = kwargs['method']
        else:
            method = args[0]

        if 'url' in kwargs:
            url = kwargs['url']
        else:
            url = args[1]

        signature = method.upper()

        if url:
            parsed_url = urlparse.urlparse(url)
            host = parsed_url.hostname or " "
            signature += " " + host

            if parsed_url.port and \
               default_ports.get(parsed_url.scheme) != parsed_url.port:
                signature += ":" + str(parsed_url.port)

        with trace(signature, "ext.http.requests",
                   {'url': url}, leaf=True):
            return wrapped(*args, **kwargs)
