import random
import threading

import mock
import urllib3

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.traces import trace
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase

try:
    from http import server as SimpleHTTPServer
    from socketserver import TCPServer
except ImportError:
    import SimpleHTTPServer
    from SocketServer import TCPServer

class MyTCPServer(TCPServer):
    allow_reuse_address = True

class InstrumentUrllib3Test(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        self.port = random.randint(50000, 60000)
        self.start_test_server()
        elasticapm.instrumentation.control.instrument()

    def tearDown(self):
        if self.httpd:
            self.httpd.shutdown()

    def start_test_server(self):
        handler = SimpleHTTPServer.SimpleHTTPRequestHandler

        self.httpd = MyTCPServer(("", self.port), handler)

        self.httpd_thread = threading.Thread(target=self.httpd.serve_forever)
        self.httpd_thread.setDaemon(True)
        self.httpd_thread.start()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_urllib3(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction")
        expected_sig = 'GET localhost:{0}'.format(self.port)
        with trace("test_pipeline", "test"):
            pool = urllib3.PoolManager(timeout=0.1)

            url = 'http://localhost:{0}/hello_world'.format(self.port)
            r = pool.request('GET', url)

        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'test_pipeline', expected_sig]

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(len(traces), 3)

        self.assertEqual(traces[0]['name'], expected_sig)
        self.assertEqual(traces[0]['type'], 'ext.http.urllib3')
        self.assertEqual(traces[0]['context']['url'], url)
        self.assertEqual(traces[0]['parent'], 1)

        self.assertEqual(traces[1]['name'], 'test_pipeline')
        self.assertEqual(traces[1]['type'], 'test')

        self.assertEqual(traces[2]['name'], 'transaction')
        self.assertEqual(traces[2]['type'], 'transaction')
