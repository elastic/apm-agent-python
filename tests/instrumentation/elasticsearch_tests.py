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

pytest.importorskip("elasticsearch")  # isort:skip

import os

from elasticsearch import VERSION as ES_VERSION
from elasticsearch import Elasticsearch

from elasticapm.conf.constants import TRANSACTION

pytestmark = pytest.mark.elasticsearch

document_type = "_doc" if ES_VERSION[0] >= 6 else "doc"


@pytest.fixture
def elasticsearch(request):
    """Elasticsearch client fixture."""
    client = Elasticsearch(hosts=os.environ["ES_URL"])
    try:
        yield client
    finally:
        client.indices.delete(index="*")


@pytest.mark.integrationtest
def test_ping(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.ping()
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES HEAD /"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"


@pytest.mark.integrationtest
def test_info(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.info()
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"


@pytest.mark.integrationtest
def test_create(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 5:
        r1 = elasticsearch.create("tweets", document_type, {"user": "kimchy", "text": "hola"}, 1)
    elif ES_VERSION[0] < 7:
        r1 = elasticsearch.create("tweets", document_type, 1, body={"user": "kimchy", "text": "hola"})
    else:
        r1 = elasticsearch.create("tweets", 1, body={"user": "kimchy", "text": "hola"})
    r2 = elasticsearch.create(
        index="tweets", doc_type=document_type, id=2, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    for i, span in enumerate(spans):
        if ES_VERSION[0] >= 5:
            assert span["name"] == "ES PUT /tweets/%s/%d/_create" % (document_type, i + 1)
        else:
            assert span["name"] == "ES PUT /tweets/%s/%d" % (document_type, i + 1)
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]


@pytest.mark.integrationtest
def test_index(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 7:
        r1 = elasticsearch.index("tweets", document_type, {"user": "kimchy", "text": "hola"})
    else:
        r1 = elasticsearch.index("tweets", {"user": "kimchy", "text": "hola"})
    r2 = elasticsearch.index(
        index="tweets", doc_type=document_type, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    for span in spans:
        assert span["name"] == "ES POST /tweets/%s" % document_type
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]


@pytest.mark.integrationtest
def test_exists(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.exists(id=1, index="tweets", doc_type=document_type)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES HEAD /tweets/%s/1" % document_type
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"


@pytest.mark.skipif(ES_VERSION[0] < 5, reason="unsupported method")
@pytest.mark.integrationtest
def test_exists_source(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 7:
        assert elasticsearch.exists_source("tweets", document_type, 1) is True
    else:
        assert elasticsearch.exists_source("tweets", 1, document_type) is True
    assert elasticsearch.exists_source(index="tweets", doc_type=document_type, id=1) is True
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    for span in spans:
        assert span["name"] == "ES HEAD /tweets/%s/1/_source" % document_type
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]


@pytest.mark.integrationtest
def test_get(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    # this is a fun one. Order pre-6x was (index, id, doc_type), changed to (index, doc_type, id) in 6.x, and reverted
    # to (index, id, doc_type) in 7.x. OK then.
    if ES_VERSION[0] == 6:
        r1 = elasticsearch.get("tweets", document_type, 1)
    else:
        r1 = elasticsearch.get("tweets", 1, document_type)
    r2 = elasticsearch.get(index="tweets", doc_type=document_type, id=1)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    for r in (r1, r2):
        assert r["found"]
        assert r["_source"] == {"user": "kimchy", "text": "hola"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    for span in spans:
        assert span["name"] == "ES GET /tweets/%s/1" % document_type
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]


@pytest.mark.integrationtest
def test_get_source(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 7:
        r1 = elasticsearch.get_source("tweets", document_type, 1)
    else:
        r1 = elasticsearch.get_source("tweets", 1, document_type)
    r2 = elasticsearch.get_source(index="tweets", doc_type=document_type, id=1)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]

    for r in (r1, r2):
        assert r == {"user": "kimchy", "text": "hola"}

    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    for span in spans:
        assert span["name"] == "ES GET /tweets/%s/1/_source" % document_type
        assert span["type"] == "db"
        assert span["subtype"] == "elasticsearch"
        assert span["action"] == "query"
        assert span["context"]["db"]["type"] == "elasticsearch"
        assert "statement" not in span["context"]["db"]


@pytest.mark.skipif(ES_VERSION[0] < 5, reason="unsupported method")
@pytest.mark.integrationtest
def test_update_script(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 7:
        r1 = elasticsearch.update("tweets", document_type, 1, {"script": "ctx._source.text = 'adios'"}, refresh=True)
    else:
        r1 = elasticsearch.update("tweets", 1, document_type, {"script": "ctx._source.text = 'adios'"}, refresh=True)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    r2 = elasticsearch.get(index="tweets", doc_type=document_type, id=1)
    assert r1["result"] == "updated"
    assert r2["_source"] == {"user": "kimchy", "text": "adios"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1

    span = spans[0]
    assert span["name"] == "ES POST /tweets/%s/1/_update" % document_type
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == '{"script": "ctx._source.text = \'adios\'"}'


@pytest.mark.integrationtest
def test_update_document(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    if ES_VERSION[0] < 7:
        r1 = elasticsearch.update("tweets", document_type, 1, {"doc": {"text": "adios"}}, refresh=True)
    else:
        r1 = elasticsearch.update("tweets", 1, document_type, {"doc": {"text": "adios"}}, refresh=True)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    r2 = elasticsearch.get(index="tweets", doc_type=document_type, id=1)
    assert r2["_source"] == {"user": "kimchy", "text": "adios"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1

    span = spans[0]
    assert span["name"] == "ES POST /tweets/%s/1/_update" % document_type
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert "statement" not in span["context"]["db"]


@pytest.mark.integrationtest
def test_search_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.search(body=search_query, params=None)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["hits"]["hits"][0]["_source"] == {"user": "kimchy", "text": "hola"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    if ES_VERSION[0] < 7:
        assert span["name"] == "ES GET /_search"
    else:
        assert span["name"] == "ES GET /_all/_search"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_search_querystring(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    search_query = "user:kimchy"
    result = elasticsearch.search(q=search_query, index="tweets")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["hits"]["hits"][0]["_source"] == {"user": "kimchy", "text": "hola"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /tweets/_search"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == "q=user:kimchy"


@pytest.mark.integrationtest
def test_search_both(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    search_querystring = "text:hola"
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.search(body=search_query, q=search_querystring, index="tweets")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert len(result["hits"]["hits"]) == 1
    assert result["hits"]["hits"][0]["_source"] == {"user": "kimchy", "text": "hola"}
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /tweets/_search"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == 'q=text:hola\n\n{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_count_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.count(body=search_query)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["count"] == 1
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    if ES_VERSION[0] < 7:
        assert span["name"] == "ES GET /_count"
    else:
        assert span["name"] == "ES GET /_all/_count"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_count_querystring(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    search_query = "user:kimchy"
    result = elasticsearch.count(q=search_query, index="tweets")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    assert result["count"] == 1
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /tweets/_count"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == "q=user:kimchy"


@pytest.mark.integrationtest
def test_delete(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.delete(id=1, index="tweets", doc_type=document_type)
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    span = spans[0]
    assert span["name"] == "ES DELETE /tweets/%s/1" % document_type
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"


@pytest.mark.skipif(ES_VERSION[0] < 5, reason="unsupported method")
@pytest.mark.integrationtest
def test_delete_by_query_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(
        index="tweets", doc_type=document_type, id=1, body={"user": "kimchy", "text": "hola"}, refresh=True
    )
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.delete_by_query(index="tweets", body={"query": {"term": {"user": "kimchy"}}})
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    span = spans[0]
    assert span["name"] == "ES POST /tweets/_delete_by_query"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
    assert span["context"]["db"]["statement"] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_multiple_indexes(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index="tweets", doc_type="users", id=1, body={"user": "kimchy", "text": "hola"}, refresh=True)
    elasticsearch.create(index="snaps", doc_type="posts", id=1, body={"user": "kimchy", "text": "hola"}, refresh=True)
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.search(index=["tweets", "snaps"], q="user:kimchy")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /tweets,snaps/_search"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"


@pytest.mark.skipif(ES_VERSION[0] >= 7, reason="doc_type unsupported")
@pytest.mark.integrationtest
def test_multiple_indexes_doctypes(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index="tweets", doc_type="users", id=1, body={"user": "kimchy", "text": "hola"}, refresh=True)
    elasticsearch.create(index="snaps", doc_type="posts", id=1, body={"user": "kimchy", "text": "hola"}, refresh=True)
    elasticapm_client.begin_transaction("test")
    result = elasticsearch.search(index=["tweets", "snaps"], doc_type=["users", "posts"], q="user:kimchy")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "ES GET /tweets,snaps/users,posts/_search"
    assert span["type"] == "db"
    assert span["subtype"] == "elasticsearch"
    assert span["action"] == "query"
    assert span["context"]["db"]["type"] == "elasticsearch"
