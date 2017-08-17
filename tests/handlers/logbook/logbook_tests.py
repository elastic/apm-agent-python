import logbook

from elasticapm.handlers.logbook import LogbookHandler
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class LogbookHandlerTest(TestCase):
    def setUp(self):
        self.logger = logbook.Logger(__name__)
        self.client = get_tempstoreclient(include_paths=['tests', 'elasticapm'])
        self.handler = LogbookHandler(self.client)

    def test_logger_error_level(self):
        with self.handler.applicationbound():
            self.logger.error('This is a test error')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        assert event['log']['logger_name'] == __name__
        assert event['log']['level'] == "error"
        assert event['log']['message'] == 'This is a test error'
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        assert event['log']['param_message'] == 'This is a test error'

    def test_logger_warning_level(self):
        with self.handler.applicationbound():
            self.logger.warning('This is a test warning')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        assert event['log']['logger_name'] == __name__
        assert event['log']['level'] == "warning"
        assert event['log']['message'] == 'This is a test warning'
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        assert event['log']['param_message'] == 'This is a test warning'

    def test_logger_with_extra(self):
        with self.handler.applicationbound():
            self.logger.info('This is a test info with a url', extra=dict(
                url='http://example.com',
            ))
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['context']['custom']['url'], 'http://example.com')
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test info with a url')

    def test_logger_with_exc_info(self):
        with self.handler.applicationbound():
            try:
                raise ValueError('This is a test ValueError')
            except ValueError:
                self.logger.info('This is a test info with an exception', exc_info=True)

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]

        self.assertEquals(event['log']['message'], 'This is a test info with an exception')
        self.assertFalse('stacktrace' in event['log'])
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], 'ValueError: This is a test ValueError')
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test info with an exception')

    def test_logger_param_message(self):
        with self.handler.applicationbound():
            self.logger.info('This is a test of %s', 'args')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['log']['message'], 'This is a test of args')
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test of %s')

    def test_client_arg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = LogbookHandler(client)
        self.assertEquals(handler.client, client)

    def test_client_kwarg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = LogbookHandler(client=client)
        self.assertEquals(handler.client, client)

    def test_invalid_first_arg_type(self):
        self.assertRaises(ValueError, LogbookHandler, object)

    def test_missing_client_arg(self):
        self.assertRaises(TypeError, LogbookHandler)
