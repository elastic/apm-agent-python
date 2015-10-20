import os
import random
import shutil
import sys
import tempfile

import pytest

from opbeat.contrib.zerorpc import OpbeatMiddleware
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase

zerorpc = pytest.importorskip("zerorpc")
gevent = pytest.importorskip("gevent")



has_unsupported_pypy = (hasattr(sys, 'pypy_version_info')
                        and sys.pypy_version_info < (2, 6))


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

    @pytest.mark.skipif(has_unsupported_pypy, reason='Failure with pypy < 2.6')
    def test_zerorpc_middleware_with_reqrep(self):
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
