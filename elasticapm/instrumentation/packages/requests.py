from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils import default_ports
from elasticapm.utils.compat import urlparse


def get_host_from_url(url):
    parsed_url = urlparse.urlparse(url)
    host = parsed_url.hostname or " "

    if parsed_url.port and default_ports.get(parsed_url.scheme) != parsed_url.port:
        host += ":" + str(parsed_url.port)

    return host


class RequestsInstrumentation(AbstractInstrumentedModule):
    name = "requests"

    instrument_list = [("requests.sessions", "Session.send")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "request" in kwargs:
            request = kwargs["request"]
        else:
            request = args[0]

        signature = request.method.upper()
        signature += " " + get_host_from_url(request.url)

        with capture_span(signature, "ext.http.requests", {"url": request.url}, leaf=True):
            return wrapped(*args, **kwargs)
