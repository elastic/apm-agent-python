import tornado
from tornado.testing import AsyncHTTPTestCase

from elasticapm.contrib.tornado import ApiElasticHandlerAPM, TornadoApm


class MainTest1(ApiElasticHandlerAPM):

    def get(self, *args, **kwargs):
        self.write({'status': 'ok'})
        self.finish()


class MainTest2(ApiElasticHandlerAPM):

    def __raise_exception(self):
        raise Exception("Value Error")

    def get(self):
        self.__raise_exception()

    def post(self):
        self.__raise_exception()


def make_app():
    settings = {'ELASTIC_APM':
                    {'SERVICE_NAME': 'Teste tornado',
                     'SECRET_TOKEN': '',
                     "Debug": False},
                "compress_response": True,
                }
    application = tornado.web.Application([
        (r"/", MainTest1),
        (r"/error", MainTest2),
    ], **settings)
    TornadoApm(application)
    return application


class BaseTestClassTornado(AsyncHTTPTestCase):

    def get_app(self):
        return make_app()
