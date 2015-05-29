from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


_default_ports = {
    "https": 433,
    "http": 80
}

class Urllib3Instrumentation(AbstractInstrumentedModule):
    name = 'urllib3'

    instrument_list = [
        ("urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        if 'method' in kwargs:
            method = kwargs['method']
        else:
            method = args[0]

        host = instance.host

        if instance.port != _default_ports.get(instance.scheme):
            host += ":" + str(instance.port)

        if 'url' in kwargs:
            url = kwargs['url']
        else:
            url = args[1]

        signature = method.upper() + " " + host

        url = instance.scheme + "://" + host + url

        with self.client.capture_trace(signature, "ext.http.urllib3", {'url': url}):
            return wrapped(*args, **kwargs)

