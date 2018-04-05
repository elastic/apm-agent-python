import mock
import urllib3

from elasticapm.traces import capture_span
from elasticapm.utils.compat import urlparse


@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_urllib3(should_collect, instrument, elasticapm_client, httpserver):
    should_collect.return_value = False
    httpserver.serve_content('')
    url = httpserver.url + '/hello_world'
    parsed_url = urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = 'GET {0}'.format(parsed_url.netloc)
    with capture_span("test_pipeline", "test"):
        pool = urllib3.PoolManager(timeout=0.1)

        url = 'http://{0}/hello_world'.format(parsed_url.netloc)
        r = pool.request('GET', url)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']

    expected_signatures = {'test_pipeline', expected_sig}

    assert {t['name'] for t in spans} == expected_signatures

    assert len(spans) == 2

    assert spans[0]['name'] == expected_sig
    assert spans[0]['type'] == 'ext.http.urllib3'
    assert spans[0]['context']['url'] == url
    assert spans[0]['parent'] == 0

    assert spans[1]['name'] == 'test_pipeline'
    assert spans[1]['type'] == 'test'
