#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import pytest  # isort:skip

from tests.instrumentation.elasticsearch_tests import get_kwargs

pytest.importorskip("elasticsearch._async")  # isort:skip

import json
import os
import urllib.parse

from elasticsearch import VERSION as ES_VERSION
from elasticsearch import AsyncElasticsearch

from elasticapm.conf.constants import TRANSACTION

pytestmark = [pytest.mark.elasticsearch, pytest.mark.asyncio, pytest.mark.integrationtest]

if "ES_URL" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping elasticsearch test, no ES_URL environment variable"))


document_type = "_doc" if ES_VERSION[0] >= 6 else "doc"


@pytest.fixture
async def async_elasticsearch(request):
    """AsyncElasticsearch client fixture."""
    client = AsyncElasticsearch(hosts=os.environ["ES_URL"])
    try:
        yield client
    finally:
        await client.indices.delete(index="*")
        await client.close()


async def test_ping(instrument, elasticapm_client, async_elasticsearch):
    elasticapm_client.begin_transaction("test")
    result = await async_elasticsearch.ping()
    elasticapm_client.end_transaction("test", "OK")
    parsed_url = urllib.parse.urlparse(os.environ["ES_URL"])

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES HEAD /"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["sync"] is False
    assert span["context"]["destination"] == {
        "address": parsed_url.hostname,
        "port": parsed_url.port,
        "service": {"name": "", "resource": "elasticsearch", "type": ""},
    }
    assert span["context"]["http"]["status_code"] == 200


async def test_info(instrument, elasticapm_client, async_elasticsearch):
    elasticapm_client.begin_transaction("test")
    result = await async_elasticsearch.info()
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["sync"] is False
    assert span["context"]["http"]["status_code"] == 200


async def test_create(instrument, elasticapm_client, async_elasticsearch):
    elasticapm_client.begin_transaction("test")
    responses = []
    iid = lambda: str(len(responses) + 1)
    if ES_VERSION[0] < 5:
        responses.append(
            await async_elasticsearch.create("tweets", document_type, {"user": "kimchy", "text": "hola"}, iid())
        )
    elif ES_VERSION[0] < 7:
        responses.append(
            await async_elasticsearch.create("tweets", document_type, iid(), body={"user": "kimchy", "text": "hola"})
        )
    elif ES_VERSION[0] < 8:
        responses.append(await async_elasticsearch.create("tweets", iid(), body={"user": "kimchy", "text": "hola"}))
    else:
        pass  # elasticsearch-py 8+ doesn't support positional arguments
    responses.append(
        await async_elasticsearch.create(index="tweets", id=iid(), **get_kwargs({"user": "kimchy", "text": "hola"}))
    )
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == len(responses)

    for i, span in enumerate(spans):
        if ES_VERSION[0] >= 5:
            assert span["name"] in (
                "ES PUT /tweets/%s/%d/_create" % (document_type, i + 1),
                "ES PUT /tweets/_create/%d" % (i + 1),
            )
        else:
            assert span["name"] == "ES PUT /tweets/%s/%d" % (document_type, i + 1)
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]
        assert span["context"]["http"]["status_code"] == 201


async def test_search_body(instrument, elasticapm_client, async_elasticsearch):
    await async_elasticsearch.create(
        index="tweets", id="1", refresh=True, **get_kwargs({"user": "kimchy", "text": "hola", "userid": 1})
    )
    elasticapm_client.begin_transaction("test")
    search_query = {"query": {"term": {"user": "kimchy"}}, "sort": ["userid"]}
    result = await async_elasticsearch.search(body=search_query, params=None)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["hits"]["hits"][0]["_source"] == {"user": "kimchy", "text": "hola", "userid": 1}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    # Depending on ES_VERSION, could be /_all/_search or /_search, and GET or POST
    assert span["name"] in ("ES GET /_search", "ES GET /_all/_search", "ES POST /_search")
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert json.loads(span["context"]["db"]["statement"]) == json.loads(
        '{"sort": ["userid"], "query": {"term": {"user": "kimchy"}}}'
    ) or json.loads(span["context"]["db"]["statement"]) == json.loads(
        '{"query": {"term": {"user": "kimchy"}}, "sort": ["userid"]}'
    )
    assert span["sync"] is False
    if ES_VERSION[0] >= 7:
        assert span["context"]["db"]["rows_affected"] == 1
    assert span["context"]["http"]["status_code"] == 200


async def test_count_body(instrument, elasticapm_client, async_elasticsearch):
    await async_elasticsearch.create(
        index="tweets", id="1", refresh=True, **get_kwargs({"user": "kimchy", "text": "hola"})
    )
    elasticapm_client.begin_transaction("test")
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = await async_elasticsearch.count(body=search_query)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["count"] == 1
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] in ("ES GET /_count", "ES POST /_count", "ES GET /_all/_count")
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert json.loads(span["context"]["db"]["statement"]) == json.loads('{"query": {"term": {"user": "kimchy"}}}')
    assert span["sync"] is False
    assert span["context"]["http"]["status_code"] == 200
