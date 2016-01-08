import threading

import mock
import urllib3

import opbeat
import opbeat.instrumentation.control
from opbeat.traces import trace
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
        self.port = 59990
        self.start_test_server()
        opbeat.instrumentation.control.instrument()

    def tearDown(self):
        if self.httpd:
            self.httpd.shutdown()

    def start_test_server(self):
        handler = SimpleHTTPServer.SimpleHTTPRequestHandler

        self.httpd = MyTCPServer(("", self.port), handler)

        self.httpd_thread = threading.Thread(target=self.httpd.serve_forever)
        self.httpd_thread.setDaemon(True)
        self.httpd_thread.start()

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_urllib3(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction")
        expected_sig = 'GET localhost:{0}'.format(self.port)
        with trace("test_pipeline", "test"):
            pool = urllib3.PoolManager(timeout=0.1)

            url = 'http://localhost:{0}/hello_world'.format(self.port)
            r = pool.request('GET', url)

        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'test_pipeline', expected_sig]

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(len(traces), 3)

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'MyView')

        self.assertEqual(traces[1]['signature'], 'test_pipeline')
        self.assertEqual(traces[1]['kind'], 'test')
        self.assertEqual(traces[1]['transaction'], 'MyView')

        self.assertEqual(traces[2]['signature'], expected_sig)
        self.assertEqual(traces[2]['kind'], 'ext.http.urllib3')
        self.assertEqual(traces[2]['transaction'], 'MyView')

        self.assertEqual(traces[2]['extra']['url'], url)
