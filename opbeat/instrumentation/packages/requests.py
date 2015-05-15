import urlparse

from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


class RequestsInstrumentation(AbstractInstrumentedModule):
    name = 'requests'

    instrument_list = [
        ("requests.sessions", "Session.request"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        if 'method' in kwargs:
            method = kwargs['method']
        else:
            method = args[0]

        if 'url' in kwargs:
            url = kwargs['url']
        else:
            url = args[1]

        signature = method.upper()

        host = urlparse.urlparse(url).netloc
        signature += " " + host

        with self.client.capture_trace(signature, "ext.http", {'url': url}):
            return wrapped(*args, **kwargs)

