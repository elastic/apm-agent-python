import threading

import mock
import urllib3
import pytest


from elasticapm.traces import trace
from tests.fixtures import test_client


try:
    from http import server as SimpleHTTPServer
    from socketserver import TCPServer
except ImportError:
    import SimpleHTTPServer
    from SocketServer import TCPServer


class MyTCPServer(TCPServer):
    allow_reuse_address = True


@pytest.fixture(scope='module')
def tcp_server():
    handler = SimpleHTTPServer.SimpleHTTPRequestHandler
    httpd = MyTCPServer(("", 0), handler)
    httpd_thread = threading.Thread(target=httpd.serve_forever)
    httpd_thread.setDaemon(True)
    httpd_thread.start()
    yield ('localhost', httpd.socket.getsockname()[1])
    httpd.shutdown()


@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_urllib3(should_collect, test_client, tcp_server):
    should_collect.return_value = False
    host, port = tcp_server
    test_client.begin_transaction("transaction")
    expected_sig = 'GET {0}:{1}'.format(host, port)
    with trace("test_pipeline", "test"):
        pool = urllib3.PoolManager(timeout=0.1)

        url = 'http://{0}:{1}/hello_world'.format(host, port)
        r = pool.request('GET', url)

    test_client.end_transaction("MyView")

    transactions = test_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'test_pipeline', expected_sig}

    assert {t['name'] for t in traces} == expected_signatures

    assert len(traces) == 2

    assert traces[0]['name'] == expected_sig
    assert traces[0]['type'] == 'ext.http.urllib3'
    assert traces[0]['context']['url'] == url
    assert traces[0]['parent'] == 0

    assert traces[1]['name'] == 'test_pipeline'
    assert traces[1]['type'] == 'test'
