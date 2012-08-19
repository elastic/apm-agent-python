import gevent
import os
import random
import shutil
import tempfile
import unittest2
import zerorpc

from opbeat_python.base import Client
from opbeat_python.contrib.zerorpc import OpbeatMiddleware

from tests.helpers import get_tempstoreclient

class ZeroRPCTest(unittest2.TestCase):

    def setUp(self):
        self._socket_dir = tempfile.mkdtemp(prefix='opbeat_pythonzerorpcunittest')
        self._server_endpoint = 'ipc://{0}'.format(os.path.join(
                    self._socket_dir, 'random_zeroserver'
        ))

        self._sentry = get_tempstoreclient()
        zerorpc.Context.get_instance().register_middleware(OpbeatMiddleware(
                    client=self._sentry
        ))

        self._server = zerorpc.Server(random)
        self._server.bind(self._server_endpoint)
        gevent.spawn(self._server.run)

        self._client = zerorpc.Client()
        self._client.connect(self._server_endpoint)

    def test_zerorpc_middleware(self):
        try:
            self._client.choice([])
        except zerorpc.exceptions.RemoteError as ex:
            self.assertEqual(ex.name, 'IndexError')
            self.assertEqual(len(self._sentry.events), 1)
            exc = self._sentry.events[0]['exception']
            self.assertEqual(exc['type'], 'IndexError')
            frames = self._sentry.events[0]['stacktrace']['frames']
            self.assertEqual(frames[0]['function'], 'choice')
            self.assertEqual(frames[0]['module'], 'random')
            return

        self.fail('An IndexError exception should have been raised an catched')

    def tearDown(self):
        self._client.close()
        self._server.close()
        shutil.rmtree(self._socket_dir, ignore_errors=True)
