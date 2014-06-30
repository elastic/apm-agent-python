import os
import random
import shutil
import tempfile
from opbeat.utils import six
if six.PY2:
    import zerorpc  # no python 3 support for zerorpc

from opbeat.utils.compat import TestCase
from opbeat.contrib.zerorpc import OpbeatMiddleware
from opbeat.utils.compat import skipIf

from tests.helpers import get_tempstoreclient

@skipIf(six.PY3, "no zerorpc/gevent for Python3")
class ZeroRPCTest(TestCase):
    def setUp(self):
        self._socket_dir = tempfile.mkdtemp(prefix='opbeatzerorpcunittest')
        self._server_endpoint = 'ipc://{0}'.format(os.path.join(
                    self._socket_dir, 'random_zeroserver'
        ))

        self._opbeat = get_tempstoreclient()
        zerorpc.Context.get_instance().register_middleware(OpbeatMiddleware(
                    client=self._opbeat
        ))

    def test_zerorpc_middleware_with_reqrep(self):
        import gevent

        self._server = zerorpc.Server(random)
        self._server.bind(self._server_endpoint)
        gevent.spawn(self._server.run)

        self._client = zerorpc.Client()
        self._client.connect(self._server_endpoint)

        try:
            self._client.choice([])
        except zerorpc.exceptions.RemoteError as ex:
            self.assertEqual(ex.name, 'IndexError')
            self.assertEqual(len(self._opbeat.events), 1)
            exc = self._opbeat.events[0]['exception']
            self.assertEqual(exc['type'], 'IndexError')
            frames = self._opbeat.events[0]['stacktrace']['frames']
            self.assertEqual(frames[0]['function'], 'choice')
            self.assertEqual(frames[0]['module'], 'random')
            return

        self.fail('An IndexError exception should have been raised an catched')

    def tearDown(self):
        self._client.close()
        self._server.close()
        shutil.rmtree(self._socket_dir, ignore_errors=True)
