import pytest  # isort:skip
pytest.importorskip("elasticsearch")  # isort:skip

import os

from elasticsearch import VERSION as ES_VERSION
from elasticsearch import Elasticsearch

pytestmark = pytest.mark.elasticsearch


@pytest.fixture
def elasticsearch(request):
    """Elasticsearch client fixture."""
    client = Elasticsearch(hosts=os.environ['ES_URL'])
    yield client
    client.indices.delete(index='*')


@pytest.mark.integrationtest
def test_ping(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.ping()
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES HEAD /'
    assert span.type == 'db.elasticsearch'


@pytest.mark.integrationtest
def test_info(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.info()
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /'
    assert span.type == 'db.elasticsearch'


@pytest.mark.integrationtest
def test_create(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction('test')
    if ES_VERSION[0] < 5:
        r1 = elasticsearch.create('tweets', 'doc', {'user': 'kimchy', 'text': 'hola'}, 1)
    else:
        r1 = elasticsearch.create('tweets', 'doc', 1, body={'user': 'kimchy', 'text': 'hola'})
    r2 = elasticsearch.create(index='tweets', doc_type='doc', id=2, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    assert len(transaction_obj.spans) == 2

    for i, span in enumerate(transaction_obj.spans):
        if ES_VERSION[0] >= 5:
            assert span.name == 'ES PUT /tweets/doc/%d/_create' % (i + 1)
        else:
            assert span.name == 'ES PUT /tweets/doc/%d' % (i + 1)
        assert span.type == 'db.elasticsearch'
        assert span.context['db']['type'] == 'elasticsearch'
        assert 'statement' not in span.context['db']


@pytest.mark.integrationtest
def test_index(instrument, elasticapm_client, elasticsearch):
    elasticapm_client.begin_transaction('test')
    r1 = elasticsearch.index('tweets', 'doc', {'user': 'kimchy', 'text': 'hola'})
    r2 = elasticsearch.index(index='tweets', doc_type='doc', body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    assert len(transaction_obj.spans) == 2

    for span in transaction_obj.spans:
        assert span.name == 'ES POST /tweets/doc'
        assert span.type == 'db.elasticsearch'
        assert span.context['db']['type'] == 'elasticsearch'
        assert 'statement' not in span.context['db']


@pytest.mark.integrationtest
def test_exists(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.exists(id=1, index='tweets', doc_type='doc')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert result
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES HEAD /tweets/doc/1'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'


@pytest.mark.skipif(ES_VERSION[0] < 5, reason='unsupported method')
@pytest.mark.integrationtest
def test_exists_source(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    assert elasticsearch.exists_source('tweets', 'doc', 1) is True
    assert elasticsearch.exists_source(index='tweets', doc_type='doc', id=1) is True
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    assert len(transaction_obj.spans) == 2

    for span in transaction_obj.spans:
        assert span.name == 'ES HEAD /tweets/doc/1/_source'
        assert span.type == 'db.elasticsearch'
        assert span.context['db']['type'] == 'elasticsearch'
        assert 'statement' not in span.context['db']


@pytest.mark.integrationtest
def test_get(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    if ES_VERSION[0] >= 6:
        r1 = elasticsearch.get('tweets', 'doc', 1)
    else:
        r1 = elasticsearch.get('tweets', 1, 'doc')
    r2 = elasticsearch.get(index='tweets', doc_type='doc', id=1)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    for r in (r1, r2):
        assert r['found']
        assert r['_source'] == {'user': 'kimchy', 'text': 'hola'}
    assert len(transaction_obj.spans) == 2

    for span in transaction_obj.spans:
        assert span.name == 'ES GET /tweets/doc/1'
        assert span.type == 'db.elasticsearch'
        assert span.context['db']['type'] == 'elasticsearch'
        assert 'statement' not in span.context['db']


@pytest.mark.integrationtest
def test_get_source(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    r1 = elasticsearch.get_source('tweets', 'doc', 1)
    r2 = elasticsearch.get_source(index='tweets', doc_type='doc', id=1)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')

    for r in (r1, r2):
        assert r == {'user': 'kimchy', 'text': 'hola'}

    assert len(transaction_obj.spans) == 2

    for span in transaction_obj.spans:
        assert span.name == 'ES GET /tweets/doc/1/_source'
        assert span.type == 'db.elasticsearch'
        assert span.context['db']['type'] == 'elasticsearch'
        assert 'statement' not in span.context['db']


@pytest.mark.skipif(ES_VERSION[0] < 5, reason='unsupported method')
@pytest.mark.integrationtest
def test_update_script(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    r1 = elasticsearch.update('tweets', 'doc', 1, {'script': "ctx._source.text = 'adios'"}, refresh=True)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    r2 = elasticsearch.get(index='tweets', doc_type='doc', id=1)
    assert r1['result'] == 'updated'
    assert r2['_source'] == {'user': 'kimchy', 'text': 'adios'}
    assert len(transaction_obj.spans) == 1

    span = transaction_obj.spans[0]
    assert span.name == 'ES POST /tweets/doc/1/_update'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == '{"script": "ctx._source.text = \'adios\'"}'


@pytest.mark.integrationtest
def test_update_document(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    r1 = elasticsearch.update('tweets', 'doc', 1, {'doc': {'text': 'adios'}}, refresh=True)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    r2 = elasticsearch.get(index='tweets', doc_type='doc', id=1)
    assert r2['_source'] == {'user': 'kimchy', 'text': 'adios'}
    assert len(transaction_obj.spans) == 1

    span = transaction_obj.spans[0]
    assert span.name == 'ES POST /tweets/doc/1/_update'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert 'statement' not in span.context['db']


@pytest.mark.integrationtest
def test_search_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.search(body=search_query)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert result['hits']['hits'][0]['_source'] == {'user': 'kimchy', 'text': 'hola'}
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /_search'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_search_querystring(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    search_query = 'user:kimchy'
    result = elasticsearch.search(q=search_query, index='tweets')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert result['hits']['hits'][0]['_source'] == {'user': 'kimchy', 'text': 'hola'}
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /tweets/_search'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == 'q=user:kimchy'


@pytest.mark.integrationtest
def test_search_both(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    search_querystring = 'text:hola'
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.search(body=search_query, q=search_querystring, index='tweets')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert len(result['hits']['hits']) == 1
    assert result['hits']['hits'][0]['_source'] == {'user': 'kimchy', 'text': 'hola'}
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /tweets/_search'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == 'q=text:hola\n\n{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_count_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    search_query = {"query": {"term": {"user": "kimchy"}}}
    result = elasticsearch.count(body=search_query)
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert result['count'] == 1
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /_count'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_count_querystring(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    search_query = 'user:kimchy'
    result = elasticsearch.count(q=search_query, index='tweets')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert result['count'] == 1
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /tweets/_count'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == 'q=user:kimchy'


@pytest.mark.integrationtest
def test_delete(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.delete(id=1, index='tweets', doc_type='doc')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    span = transaction_obj.spans[0]
    assert span.name == 'ES DELETE /tweets/doc/1'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'


@pytest.mark.skipif(ES_VERSION[0] < 5, reason='unsupported method')
@pytest.mark.integrationtest
def test_delete_by_query_body(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='doc', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.delete_by_query(index='tweets', body={"query": {"term": {"user": "kimchy"}}})
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    span = transaction_obj.spans[0]
    assert span.name == 'ES POST /tweets/_delete_by_query'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
    assert span.context['db']['statement'] == '{"term": {"user": "kimchy"}}'


@pytest.mark.integrationtest
def test_multiple_indexes_doctypes(instrument, elasticapm_client, elasticsearch):
    elasticsearch.create(index='tweets', doc_type='users', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticsearch.create(index='snaps', doc_type='posts', id=1, body={'user': 'kimchy', 'text': 'hola'}, refresh=True)
    elasticapm_client.begin_transaction('test')
    result = elasticsearch.search(index=['tweets','snaps'], doc_type=['users','posts'], q='user:kimchy')
    transaction_obj = elasticapm_client.end_transaction('test', 'OK')
    assert len(transaction_obj.spans) == 1
    span = transaction_obj.spans[0]
    assert span.name == 'ES GET /tweets,snaps/users,posts/_search'
    assert span.type == 'db.elasticsearch'
    assert span.context['db']['type'] == 'elasticsearch'
