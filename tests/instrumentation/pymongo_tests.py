import datetime
import os

import pymongo
import pytest


@pytest.fixture()
def mongo_database():
    connection_params = {'host': os.environ.get('MONGODB_HOST', 'localhost'),
                         'port': int(os.environ.get('MONGODB_PORT', 27017))}
    if pymongo.version_tuple < (3, 0):
        connection_params['safe'] = True
    mongo = pymongo.MongoClient(**connection_params)
    db = mongo.elasticapm_test
    yield db
    mongo.drop_database('elasticapm_test')
    mongo.close()


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_bulk_write(elasticapm_client, mongo_database):
    elasticapm_client.begin_transaction('transaction.test')
    requests = [pymongo.InsertOne({'x': 1}),
                pymongo.DeleteOne({'x': 1}),
                pymongo.ReplaceOne({'w': 1}, {'z': 1}, upsert=True)]
    result = mongo_database.blogposts.bulk_write(requests)
    assert result.inserted_count == 1
    assert result.deleted_count == 1
    assert result.upserted_count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.bulk_write'


@pytest.mark.integrationtest
def test_collection_count(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    mongo_database.blogposts.insert(blogpost)
    elasticapm_client.instrumentation_store.get_all()
    elasticapm_client.begin_transaction('transaction.test')
    count = mongo_database.blogposts.count()
    assert count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.count'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_delete_one(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.delete_one({'author': 'Tom'})
    assert r.deleted_count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.delete_one'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_delete_many(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.delete_many({'author': 'Tom'})
    assert r.deleted_count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.delete_many'


@pytest.mark.integrationtest
def test_collection_insert(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.insert(blogpost)
    assert r is not None
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.insert'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_insert_one(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.insert_one(blogpost)
    assert r.inserted_id is not None
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.insert_one'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_insert_many(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.insert_many([blogpost])
    assert len(r.inserted_ids) == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()

    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.insert_many'


@pytest.mark.integrationtest
def test_collection_find(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    blogposts = []
    for i in range(1000):
        blogposts.append({'author': 'Tom', 'comments': i})
    mongo_database.blogposts.insert(blogposts)
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.instrumentation_store.get_all()
    elasticapm_client.begin_transaction('transaction.test')
    r = list(mongo_database.blogposts.find({'comments': {'$gt': 995}}))

    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.cursor.refresh'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_find_one(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.find_one({'author': 'Tom'})
    assert r['author'] == 'Tom'
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.find_one'


@pytest.mark.integrationtest
def test_collection_remove(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.remove({'author': 'Tom'})
    assert r['n'] == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.remove'


@pytest.mark.integrationtest
def test_collection_update(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.update({'author': 'Tom'},
                                 {'$set': {'author': 'Jerry'}})
    assert r['n'] == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.update'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_update_one(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.update_one({'author': 'Tom'},
                                 {'$set': {'author': 'Jerry'}})
    assert r.modified_count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.update_one'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
def test_collection_update_many(elasticapm_client, mongo_database):
    blogpost = {'author': 'Tom', 'text': 'Foo',
                'date': datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction('transaction.test')
    r = mongo_database.blogposts.update_many({'author': 'Tom'},
                                 {'$set': {'author': 'Jerry'}})
    assert r.modified_count == 1
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.blogposts.update_many'


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (2, 7), reason='New in 2.7')
def test_bulk_execute(elasticapm_client, mongo_database):
    elasticapm_client.begin_transaction('transaction.test')
    bulk = mongo_database.test_bulk.initialize_ordered_bulk_op()
    bulk.insert({'x': 'y'})
    bulk.insert({'z': 'x'})
    bulk.find({'x': 'y'}).replace_one({'x': 'z'})
    bulk.execute()
    elasticapm_client.end_transaction('transaction.test')
    transactions = elasticapm_client.instrumentation_store.get_all()
    trace = _get_pymongo_trace(transactions[0]['traces'])
    assert trace['type'] == 'db.mongodb.query'
    assert trace['name'] == 'elasticapm_test.test_bulk.bulk.execute'


def _get_pymongo_trace(traces):
    for trace in traces:
        if trace['type'].startswith('db.mongodb'):
            return trace
