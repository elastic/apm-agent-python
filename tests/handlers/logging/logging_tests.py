import logging

from opbeat.handlers.logging import OpbeatHandler
from opbeat.utils.stacks import iter_stack_frames
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class LoggingIntegrationTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient(include_paths=['tests', 'opbeat'])
        self.handler = OpbeatHandler(self.client)
        self.logger = logging.getLogger(__name__)
        self.logger.handlers = []
        self.logger.addHandler(self.handler)

    def test_logger_basic(self):
        self.logger.error('This is a test error')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['logger'], __name__)
        self.assertEquals(event['level'], "error")
        self.assertEquals(event['message'], 'This is a test error')
        self.assertFalse('stacktrace' in event)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test error')
        self.assertEquals(msg['params'], ())

    def test_logger_warning(self):
        self.logger.warning('This is a test warning')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['logger'], __name__)
        self.assertEquals(event['level'], "warning")
        self.assertFalse('stacktrace' in event)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test warning')
        self.assertEquals(msg['params'], ())

    def test_logger_extra_data(self):
        self.logger.info('This is a test info with a url', extra=dict(
            data=dict(
                url='http://example.com',
            ),
        ))
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['extra']['url'], 'http://example.com')
        self.assertFalse('stacktrace' in event)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test info with a url')
        self.assertEquals(msg['params'], ())

    def test_logger_exc_info(self):
        try:
            raise ValueError('This is a test ValueError')
        except ValueError:
            self.logger.info('This is a test info with an exception', exc_info=True)

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)

        # self.assertEquals(event['message'], 'This is a test info with an exception')
        self.assertTrue('stacktrace' in event)
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], 'This is a test ValueError')
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test info with an exception')
        self.assertEquals(msg['params'], ())

    def test_message_params(self):
        self.logger.info('This is a test of %s', 'args')
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        # self.assertEquals(event['message'], 'This is a test of args')
        # print event.keys()
        self.assertFalse('stacktrace' in event)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test of %s')
        self.assertEquals(msg['params'], ('args',))

    def test_record_stack(self):
        self.logger.info('This is a test of stacks', extra={'stack': True})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertTrue('stacktrace' in event)
        frames = event['stacktrace']['frames']
        self.assertNotEquals(len(frames), 1)
        frame = frames[0]
        self.assertEquals(frame['module'], __name__)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test of stacks')
        self.assertEquals(msg['params'], ())
        self.assertEquals(event['culprit'], 'tests.handlers.logging.logging_tests.test_record_stack')
        self.assertEquals(event['message'], 'This is a test of stacks')

    def test_no_record_stack(self):
        self.logger.info('This is a test of no stacks', extra={'stack': False})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event.get('culprit'), None)
        self.assertEquals(event['message'], 'This is a test of no stacks')
        self.assertFalse('stacktrace' in event)
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test of no stacks')
        self.assertEquals(msg['params'], ())

    def test_explicit_stack(self):
        self.logger.info('This is a test of stacks', extra={'stack': iter_stack_frames()})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertTrue('culprit' in event, event)
        self.assertEquals(event['culprit'], 'tests.handlers.logging.logging_tests.test_explicit_stack')
        self.assertTrue('message' in event, event)
        self.assertEquals(event['message'], 'This is a test of stacks')
        self.assertFalse('exception' in event)
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test of stacks')
        self.assertEquals(msg['params'], ())
        self.assertTrue('stacktrace' in event)

    def test_extra_culprit(self):
        self.logger.info('This is a test of stacks', extra={'culprit': 'foo.bar'})
        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)
        self.assertEquals(event['culprit'], 'foo.bar')

    def test_logger_exception(self):
        try:
            raise ValueError('This is a test ValueError')
        except ValueError:
            self.logger.exception('This is a test with an exception')

        self.assertEquals(len(self.client.events), 1)
        event = self.client.events.pop(0)

        self.assertEquals(event['message'], 'This is a test with an exception')
        self.assertTrue('stacktrace' in event)
        self.assertTrue('exception' in event)
        exc = event['exception']
        self.assertEquals(exc['type'], 'ValueError')
        self.assertEquals(exc['value'], 'This is a test ValueError')
        self.assertTrue('param_message' in event)
        msg = event['param_message']
        self.assertEquals(msg['message'], 'This is a test with an exception')
        self.assertEquals(msg['params'], ())


class LoggingHandlerTest(TestCase):
    def test_client_arg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = OpbeatHandler(client)
        self.assertEquals(handler.client, client)

    def test_client_kwarg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = OpbeatHandler(client=client)
        self.assertEquals(handler.client, client)

    def test_invalid_first_arg_type(self):
        self.assertRaises(ValueError, OpbeatHandler, object)
