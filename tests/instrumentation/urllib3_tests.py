import mock
import urllib3

from elasticapm.conf.constants import TRANSACTION
from elasticapm.traces import capture_span
from elasticapm.utils.compat import urlparse


def test_urllib3(instrument, elasticapm_client, waiting_httpserver):
    waiting_httpserver.serve_content("")
    url = waiting_httpserver.url + "/hello_world"
    parsed_url = urlparse.urlparse(url)
    elasticapm_client.begin_transaction("transaction")
    expected_sig = "GET {0}".format(parsed_url.netloc)
    with capture_span("test_pipeline", "test"):
        pool = urllib3.PoolManager(timeout=0.1)

        url = "http://{0}/hello_world".format(parsed_url.netloc)
        r = pool.request("GET", url)

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"test_pipeline", expected_sig}

    assert {t["name"] for t in spans} == expected_signatures

    assert len(spans) == 2

    assert spans[0]["name"] == expected_sig
    assert spans[0]["type"] == "ext.http.urllib3"
    assert spans[0]["context"]["url"] == url
    assert spans[0]["parent"] == 0

    assert spans[1]["name"] == "test_pipeline"
    assert spans[1]["type"] == "test"
