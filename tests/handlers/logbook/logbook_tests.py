import logbook

from opbeat.handlers.logbook import OpbeatHandler
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class LogbookHandlerTest(TestCase):
    def setUp(self):
        self.logger = logbook.Logger(__name__)

    def test_logger(self):
        client = get_tempstoreclient(include_paths=['tests', 'opbeat'])
        handler = OpbeatHandler(client)
        logger = self.logger

        with handler.applicationbound():
            logger.error('This is a test error')

            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['logger'], __name__)
            self.assertEquals(event['level'], "error")
            self.assertEquals(event['message'], 'This is a test error')
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('param_message' in event)
            msg = event['param_message']
            self.assertEquals(msg['message'], 'This is a test error')
            self.assertEquals(msg['params'], ())

            logger.warning('This is a test warning')
            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['logger'], __name__)
            self.assertEquals(event['level'], 'warning')
            self.assertEquals(event['message'], 'This is a test warning')
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('param_message' in event)
            msg = event['param_message']
            self.assertEquals(msg['message'], 'This is a test warning')
            self.assertEquals(msg['params'], ())

            logger.info('This is a test info with a url', extra=dict(
                url='http://example.com',
            ))
            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['extra']['url'], 'http://example.com')
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('param_message' in event)
            msg = event['param_message']
            self.assertEquals(msg['message'], 'This is a test info with a url')
            self.assertEquals(msg['params'], ())

            try:
                raise ValueError('This is a test ValueError')
            except ValueError:
                logger.info('This is a test info with an exception', exc_info=True)

            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)

            self.assertEquals(event['message'], 'This is a test info with an exception')
            self.assertTrue('stacktrace' in event)
            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ValueError')
            self.assertEquals(exc['value'], 'This is a test ValueError')
            self.assertTrue('param_message' in event)
            msg = event['param_message']
            self.assertEquals(msg['message'], 'This is a test info with an exception')
            self.assertEquals(msg['params'], ())

            # test args
            logger.info('This is a test of %s', 'args')
            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['message'], 'This is a test of args')
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('param_message' in event)
            msg = event['param_message']
            self.assertEquals(msg['message'], 'This is a test of %s')
            self.assertEquals(msg['params'], ('args',))

    def test_client_arg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = OpbeatHandler(client)
        self.assertEquals(handler.client, client)

    def test_client_kwarg(self):
        client = get_tempstoreclient(include_paths=['tests'])
        handler = OpbeatHandler(client=client)
        self.assertEquals(handler.client, client)

    # def test_first_arg_as_dsn(self):
    #     handler = OpbeatHandler('http://public:secret@example.com/1')
    #     self.assertTrue(isinstance(handler.client, Client))

    # def test_custom_client_class(self):
    #     handler = OpbeatHandler('http://public:secret@example.com/1', client_cls=TempStoreClient)
    #     self.assertTrue(type(handler.client), TempStoreClient)

    def test_invalid_first_arg_type(self):
        self.assertRaises(ValueError, OpbeatHandler, object)

    def test_missing_client_arg(self):
        self.assertRaises(TypeError, OpbeatHandler)
