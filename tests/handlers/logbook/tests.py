import logbook
from unittest2 import TestCase
from opbeat_python.base import Client
from opbeat_python.handlers.logbook import SentryHandler


class TempStoreClient(Client):
    def __init__(self, servers=None, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(servers=servers, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)


class LogbookHandlerTest(TestCase):
    def setUp(self):
        self.logger = logbook.Logger(__name__)

    def test_logger(self):
        client = TempStoreClient(include_paths=['tests', 'opbeat_python'])
        handler = SentryHandler(client)
        logger = self.logger

        with handler.applicationbound():
            logger.error('This is a test error')

            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['logger'], __name__)
            self.assertEquals(event['level'], logbook.ERROR)
            self.assertEquals(event['message'], {'message':'This is a test error','params':()})
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('message' in event)
            msg = event['message']
            self.assertEquals(msg['message'], 'This is a test error')
            self.assertEquals(msg['params'], ())

            logger.warning('This is a test warning')
            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            self.assertEquals(event['logger'], __name__)
            self.assertEquals(event['level'], logbook.WARNING)
            self.assertEquals(event['message'], {'message':'This is a test warning','params':()})
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('message' in event)
            msg = event['message']
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
            self.assertTrue('message' in event)
            msg = event['message']
            self.assertEquals(msg['message'], 'This is a test info with a url')
            self.assertEquals(msg['params'], ())

            try:
                raise ValueError('This is a test ValueError')
            except ValueError:
                logger.info('This is a test info with an exception', exc_info=True)

            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)

            self.assertEquals(event['message'], {'message':'This is a test info with an exception','params':()})
            self.assertTrue('stacktrace' in event)
            self.assertTrue('exception' in event)
            exc = event['exception']
            self.assertEquals(exc['type'], 'ValueError')
            self.assertEquals(exc['value'], 'This is a test ValueError')
            self.assertTrue('message' in event)
            msg = event['message']
            self.assertEquals(msg['message'], 'This is a test info with an exception')
            self.assertEquals(msg['params'], ())

            # test args
            logger.info('This is a test of %s', 'args')
            self.assertEquals(len(client.events), 1)
            event = client.events.pop(0)
            # self.assertEquals(event['message'], 'This is a test of args')
            self.assertFalse('stacktrace' in event)
            self.assertFalse('exception' in event)
            self.assertTrue('message' in event)
            msg = event['message']
            self.assertEquals(msg['message'], 'This is a test of %s')
            self.assertEquals(msg['params'], ('args',))

    def test_client_arg(self):
        client = TempStoreClient(include_paths=['tests'])
        handler = SentryHandler(client)
        self.assertEquals(handler.client, client)

    def test_client_kwarg(self):
        client = TempStoreClient(include_paths=['tests'])
        handler = SentryHandler(client=client)
        self.assertEquals(handler.client, client)

    def test_first_arg_as_dsn(self):
        handler = SentryHandler('http://public:secret@example.com/1')
        self.assertTrue(isinstance(handler.client, Client))

    def test_custom_client_class(self):
        handler = SentryHandler('http://public:secret@example.com/1', client_cls=TempStoreClient)
        self.assertTrue(type(handler.client), TempStoreClient)

    def test_invalid_first_arg_type(self):
        self.assertRaises(ValueError, SentryHandler, object)

    def test_missing_client_arg(self):
        self.assertRaises(TypeError, SentryHandler)
