import datetime
import os

import pymongo
import pytest

import opbeat
import opbeat.instrumentation.control
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentPyMongoTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        opbeat.instrumentation.control.instrument()
        connection_params = {'host': os.environ.get('MONGODB_HOST', 'localhost'),
                             'port': int(os.environ.get('MONGODB_PORT', 27017))}
        if pymongo.version_tuple < (3, 0):
            connection_params['safe'] = True
        self.mongo = pymongo.MongoClient(**connection_params)
        self.db = self.mongo.opbeat_test

    def tearDown(self):
        self.mongo.drop_database('opbeat_test')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_bulk_write(self):
        self.client.begin_transaction('transaction.test')
        requests = [pymongo.InsertOne({'x': 1}),
                    pymongo.DeleteOne({'x': 1}),
                    pymongo.ReplaceOne({'w': 1}, {'z': 1}, upsert=True)]
        result = self.db.blogposts.bulk_write(requests)
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.deleted_count, 1)
        self.assertEqual(result.upserted_count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.bulk_write')

    def test_collection_count(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.db.blogposts.insert(blogpost)
        self.client.instrumentation_store.get_all()
        self.client.begin_transaction('transaction.test')
        count = self.db.blogposts.count()
        self.assertEqual(count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'], 'opbeat_test.blogposts.count')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_delete_one(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.db.blogposts.insert_one(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.delete_one({'author': 'Tom'})
        self.assertEqual(r.deleted_count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.delete_one')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_delete_many(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.db.blogposts.insert_one(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.delete_many({'author': 'Tom'})
        self.assertEqual(r.deleted_count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.delete_many')

    def test_collection_insert(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.insert(blogpost)
        self.assertIsNotNone(r)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.insert')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_insert_one(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.insert_one(blogpost)
        self.assertIsNotNone(r.inserted_id)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.insert_one')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_insert_many(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.insert_many([blogpost])
        self.assertEqual(len(r.inserted_ids), 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()

        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.insert_many')

    def test_collection_find(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        blogposts = []
        for i in range(1000):
            blogposts.append({'author': 'Tom', 'comments': i})
        self.db.blogposts.insert(blogposts)
        r = self.db.blogposts.insert(blogpost)
        self.client.instrumentation_store.get_all()
        self.client.begin_transaction('transaction.test')
        r = list(self.db.blogposts.find({'comments': {'$gt': 995}}))

        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.cursor.refresh')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_find_one(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        r = self.db.blogposts.insert_one(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.find_one({'author': 'Tom'})
        self.assertEqual(r['author'], 'Tom')
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.find_one')

    def test_collection_remove(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        r = self.db.blogposts.insert(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.remove({'author': 'Tom'})
        self.assertEqual(r['n'], 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.remove')

    def test_collection_update(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        r = self.db.blogposts.insert(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.update({'author': 'Tom'},
                                     {'$set': {'author': 'Jerry'}})
        self.assertEqual(r['n'], 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.update')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_update_one(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        r = self.db.blogposts.insert(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.update_one({'author': 'Tom'},
                                     {'$set': {'author': 'Jerry'}})
        self.assertEqual(r.modified_count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.update_one')

    @pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason='New in 3.0')
    def test_collection_update_many(self):
        blogpost = {'author': 'Tom', 'text': 'Foo',
                    'date': datetime.datetime.utcnow()}
        r = self.db.blogposts.insert(blogpost)
        self.client.begin_transaction('transaction.test')
        r = self.db.blogposts.update_many({'author': 'Tom'},
                                     {'$set': {'author': 'Jerry'}})
        self.assertEqual(r.modified_count, 1)
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.blogposts.update_many')

    @pytest.mark.skipif(pymongo.version_tuple < (2, 7), reason='New in 2.7')
    def test_bulk_execute(self):
        self.client.begin_transaction('transaction.test')
        bulk = self.db.test_bulk.initialize_ordered_bulk_op()
        bulk.insert({'x': 'y'})
        bulk.insert({'z': 'x'})
        bulk.find({'x': 'y'}).replace_one({'x': 'z'})
        bulk.execute()
        self.client.end_transaction('transaction.test')
        transactions, traces = self.client.instrumentation_store.get_all()
        trace = _get_pymongo_trace(traces)
        self.assertEqual(trace['kind'], 'db.mongodb.query')
        self.assertEqual(trace['signature'],
                         'opbeat_test.test_bulk.bulk.execute')


def _get_pymongo_trace(traces):
    for trace in traces:
        if trace['kind'].startswith('db.mongodb'):
            return trace
