import logging

from elasticapm.handlers.logging import LoggingHandler
from elasticapm.utils.stacks import iter_stack_frames
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class LoggingIntegrationTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient(include_paths=['tests', 'elasticapm'])
        self.handler = LoggingHandler(self.client)
        self.logger = logging.getLogger(__name__)
        self.logger.handlers = []
        self.logger.addHandler(self.handler)

    def test_logger_basic(self):
        self.logger.error('This is a test error')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['log']['logger_name'], __name__)
        self.assertEquals(event['log']['level'], "error")
        self.assertEquals(event['log']['message'], 'This is a test error')
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test error')

    def test_logger_warning(self):
        self.logger.warning('This is a test warning')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['log']['logger_name'], __name__)
        self.assertEquals(event['log']['level'], "warning")
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test warning')

    def test_logger_extra_data(self):
        self.logger.info('This is a test info with a url', extra=dict(
            data=dict(
                url='http://example.com',
            ),
        ))
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['context']['custom']['url'], 'http://example.com')
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test info with a url')

    def test_logger_exc_info(self):
        try:
            raise ValueError('This is a test ValueError')
        except ValueError:
            self.logger.info('This is a test info with an exception', exc_info=True)

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]

        # self.assertEquals(event['message'], 'This is a test info with an exception')
        self.assertTrue('exception' in event)
        self.assertTrue('stacktrace' in event['exception'])
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], 'ValueError: This is a test ValueError')
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['message'], 'This is a test info with an exception')

    def test_message_params(self):
        self.logger.info('This is a test of %s', 'args')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['message'], 'This is a test of args')
        self.assertEquals(event['log']['param_message'], 'This is a test of %s')

    def test_record_stack(self):
        self.logger.info('This is a test of stacks', extra={'stack': True})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        frames = event['log']['stacktrace']
        self.assertNotEquals(len(frames), 1)
        frame = frames[0]
        self.assertEquals(frame['module'], __name__)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test of stacks')
        self.assertEquals(event['culprit'], 'tests.handlers.logging.logging_tests.test_record_stack')
        self.assertEquals(event['log']['message'], 'This is a test of stacks')

    def test_no_record_stack(self):
        self.logger.info('This is a test of no stacks', extra={'stack': False})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event.get('culprit'), None)
        self.assertEquals(event['log']['message'], 'This is a test of no stacks')
        self.assertFalse('stacktrace' in event['log'])
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test of no stacks')

    def test_explicit_stack(self):
        self.logger.info('This is a test of stacks', extra={'stack': iter_stack_frames()})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertTrue('culprit' in event, event)
        self.assertEquals(event['culprit'], 'tests.handlers.logging.logging_tests.test_explicit_stack')
        self.assertTrue('message' in event['log'], event)
        self.assertEquals(event['log']['message'], 'This is a test of stacks')
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['param_message'], 'This is a test of stacks')
        self.assertTrue('stacktrace' in event['log'])

    def test_extra_culprit(self):
        self.logger.info('This is a test of stacks', extra={'culprit': 'foo.bar'})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]
        self.assertEquals(event['culprit'], 'foo.bar')

    def test_logger_exception(self):
        try:
            raise ValueError('This is a test ValueError')
        except ValueError:
            self.logger.exception('This is a test with an exception', extra={'stack': True})

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)['errors'][0]

        self.assertEquals(event['log']['message'], 'This is a test with an exception')
        self.assertTrue('stacktrace' in event['log'])
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['message'], 'ValueError: This is a test ValueError')
        self.assertTrue('param_message' in event['log'])
        self.assertEquals(event['log']['message'], 'This is a test with an exception')


class LoggingHandlerTest(TestCase):
    def test_client_arg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = LoggingHandler(client)
        self.assertEquals(handler.client, client)

    def test_client_kwarg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = LoggingHandler(client=client)
        self.assertEquals(handler.client, client)

    def test_invalid_first_arg_type(self):
        self.assertRaises(ValueError, LoggingHandler, object)
