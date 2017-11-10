import mock
import urllib3

from elasticapm.traces import trace
from elasticapm.utils.compat import urlparse


@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_urllib3(should_collect, elasticapm_client, httpserver):
    should_collect.return_value = False
    httpserver.serve_content('')
    url = httpserver.url + '/hello_world'
    parsed_url = urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = 'GET {0}'.format(parsed_url.netloc)
    with trace("test_pipeline", "test"):
        pool = urllib3.PoolManager(timeout=0.1)

        url = 'http://{0}/hello_world'.format(parsed_url.netloc)
        r = pool.request('GET', url)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
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
