import tornado
from tornado.web import RequestHandler

import elasticapm
from elasticapm.base import Client
from elasticapm.contrib.tornado.utils import get_data_from_request, get_data_from_response


def make_client(client_cls, app, **defaults):
    config = app.settings.get('ELASTIC_APM', {})

    if 'framework_name' not in defaults:
        defaults['framework_name'] = 'tornado'
        defaults['framework_version'] = getattr(tornado, '__version__', '<0.7')

    client = client_cls(config, **defaults)
    return client


class TornadoApm(object):

    def __validate_app(self, app):
        if not app:
            raise Exception("Handle tornado invalid")

    def __init__(self, aplication=None, client=None, client_cls=Client):
        self.__validate_app(aplication)
        self.client = client
        self.client_cls = client_cls
        self.__init_app(aplication)

    def __init_app(self, app, **defaults):
        self.app = app
        if not self.client:
            self.client = make_client(self.client_cls, app, **defaults)

        if self.client.config.instrument:
            elasticapm.instrumentation.control.instrument()
            app.settings.update({"apm_elastic": self})

    def capture_exception(self, *args, **kwargs):
        assert self.client, 'capture_exception called before application configured'
        return self.client.capture_exception(*args, **kwargs)

    def capture_message(self, *args, **kwargs):
        assert self.client, 'capture_message called before application configured'
        return self.client.capture_message(*args, **kwargs)


class ApiElasticHandlerAPM(RequestHandler):

    @staticmethod
    def __parser_url(router):
        group_index = sorted(list(router.matcher.regex.groupindex.values()))
        tuple_url = ()
        url = getattr(router.matcher, '_path')
        for param in group_index:
            for key, value in router.matcher.regex.groupindex.items():
                if value == param:
                    tuple_url += (":" + key,)
                    break
        return url % tuple_url

    def capture_exception(self):
        apm_elastic = self.settings.get("apm_elastic")
        apm_elastic.client.capture_exception(
            context={
                "request": get_data_from_request(self.request)
            },
            handled=False,
        )

    def capture_message(self, message_error):
        apm_elastic = self.settings.get("apm_elastic")
        apm_elastic.client.capture_message(message_error)

    def get_url(self):
        url = None
        for router in self.application.wildcard_router.rules:
            if router.target == self.__class__:
                url = self.__parser_url(router)
                break
        return url

    def write_error(self, status_code, **kwargs):
        self.capture_exception()

    def prepare(self):
        apm_elastic = self.settings.get("apm_elastic")
        apm_elastic.client.begin_transaction("request")

    def on_finish(self):
        apm_elastic = self.settings.get("apm_elastic")
        name_trasaction = '{} {}'.format(self.request.method, self.get_url())
        status = self.get_status()
        result = 'HTTP {}xx'.format(status // 100)
        data_request = get_data_from_request(self.request)
        data_response = get_data_from_response(self)
        elasticapm.set_context(lambda: data_request, "request")
        elasticapm.set_context(lambda: data_response, "response")
        elasticapm.set_transaction_name(name_trasaction, override=False)
        elasticapm.set_transaction_result(result, override=False)
        apm_elastic.client.end_transaction()
