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


class HttpClientTornadoInstrumentation(AbstractInstrumentedModule):
    name = "tornado"

    instrument_list = [("tornado.httpclient", "HTTPResponse")]

    def call(self, module, method, wrapped, instance, args, kwargs):

        http_request_proxy = args[0]
        url = http_request_proxy.url
        duration = kwargs.get('request_time', 0)
        start_time = kwargs.get('start_time', 0)
        print("Inicio da requisicao")
        signature = "{} {}".format(http_request_proxy.method.upper(), get_host_from_url(http_request_proxy.url))
        print("start time tornado")
        with capture_span(signature, "ext.http.tornado", {"url": url}, leaf=True, start_time=start_time,
                          duration=duration):
            print("Tornado test")
            teste = wrapped(*args, **kwargs)
            return teste

        # return wrapped(*args, **kwargs)
        # http_request = kwargs.get("url", None)
        # kwargs__http = vars(http_request)
        # del kwargs__http['_body']
        # del kwargs__http['_headers']
        # del kwargs__http['_body_producer']
        # del kwargs__http['_streaming_callback']
        # del kwargs__http['_header_callback']
        # del kwargs__http['_prepare_curl_callback']
        # del kwargs__http['start_time']
        # url = http_request.url
        # signature = "{} {}".format(http_request.method.upper(), get_host_from_url(http_request.url))
        #
        # with capture_span(signature, "ext.http.tornado", {"url": url}, leaf=True):
        #     return wrapped(*args, **kwargs__http)

