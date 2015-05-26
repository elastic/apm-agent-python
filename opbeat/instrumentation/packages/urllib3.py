from opbeat.instrumentation.packages.base import AbstractInstrumentedModule


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

        if 'url' in kwargs:
            url = kwargs['url']
        else:
            url = args[1]

        # print args, kwargs
        signature = method.upper()

        # host = urlparse.urlparse(url).netloc
        signature += " " + host

        url = instance.scheme + "://" + instance.host + url

        with self.client.capture_trace(signature, "ext.http.urllib3", {'url': url}):
            return wrapped(*args, **kwargs)

