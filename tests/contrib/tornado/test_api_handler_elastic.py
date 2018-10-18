import mock

from elasticapm.contrib.tornado import ApiElasticHandlerAPM
from tests.contrib.tornado import BaseTestClass


class MockMatcher:
    _path = "test/%s/extref"


class MockWillCardRouter:
    target = ""
    matcher = MockMatcher()


class TestApiElasticHandlerAPM(BaseTestClass):

    def test_capture_exception(self):
        application = mock.MagicMock()
        request = mock.MagicMock()
        client = mock.MagicMock()
        application().settings.get.return_value = client
        handler = ApiElasticHandlerAPM(application, request)
        handler.capture_exception()
        self.assertTrue(application.called)

    def test_capture_message(self):
        application = mock.MagicMock()
        client = mock.MagicMock()
        application().settings.get.return_value = client
        request = mock.MagicMock()
        handler = ApiElasticHandlerAPM(application, request)
        message = "error"
        handler.capture_message(message)
        self.assertTrue(application.called)

    def test_write_error(self):
        application = mock.MagicMock()
        client = mock.MagicMock()
        application().settings.get.return_value = client
        request = mock.MagicMock()
        handler = ApiElasticHandlerAPM(application, request)
        handler.write_error(status_code=400)
        self.assertTrue(application.called)

    def test_prepare(self):
        application = mock.MagicMock()
        client = mock.MagicMock()
        application().settings.get.return_value = client
        request = mock.MagicMock()
        handler = ApiElasticHandlerAPM(application, request)
        handler.prepare()
        self.assertTrue(application.called)

    def test_get_url(self):
        application = mock.MagicMock()
        request = mock.MagicMock()
        handler = ApiElasticHandlerAPM(application, request)
        mock_will = MockWillCardRouter()
        mock_will.target = handler.__class__
        application.wildcard_router.rules = [mock_will]
        url = handler.get_url()
        self.assertEqual(url, 'test/<param>/extref')

    @mock.patch("elasticapm.contrib.tornado.elasticapm")
    def test_on_finish(self, mock_elastic):
        application = mock.MagicMock()
        client = mock.MagicMock()
        application().settings.get.return_value = client
        request = mock.MagicMock()
        handler = ApiElasticHandlerAPM(application, request)
        handler.get_url = mock.Mock()
        handler.on_finish()
        self.assertTrue(application.called)
        self.assertTrue(handler.get_url.called)
        self.assertTrue(mock_elastic.set_context.called)
