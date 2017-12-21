from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils import default_ports


class Urllib3Instrumentation(AbstractInstrumentedModule):
    name = 'urllib3'

    instrument_list = [
        ("urllib3.connectionpool", "HTTPConnectionPool.urlopen"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if 'method' in kwargs:
            method = kwargs['method']
        else:
            method = args[0]

        host = instance.host

        if instance.port != default_ports.get(instance.scheme):
            host += ":" + str(instance.port)

        if 'url' in kwargs:
            url = kwargs['url']
        else:
            url = args[1]

        signature = method.upper() + " " + host

        url = instance.scheme + "://" + host + url

        with capture_span(signature, "ext.http.urllib3", {'url': url}, leaf=True):
            return wrapped(*args, **kwargs)
