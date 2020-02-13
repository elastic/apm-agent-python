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

import datetime
import os

import pytest

from elasticapm.conf.constants import TRANSACTION

pymongo = pytest.importorskip("pymongo")


pytestmark = [pytest.mark.mongodb]

if "MONGODB_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping mongodb tests, no MONGODB_HOST environment variable set"))


@pytest.fixture()
def mongo_database():
    connection_params = {
        "host": os.environ.get("MONGODB_HOST", "localhost"),
        "port": int(os.environ.get("MONGODB_PORT", 27017)),
    }
    if pymongo.version_tuple < (3, 0):
        connection_params["safe"] = True
    mongo = pymongo.MongoClient(**connection_params)
    db = mongo.elasticapm_test
    yield db
    mongo.drop_database("elasticapm_test")
    mongo.close()


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_bulk_write(instrument, elasticapm_client, mongo_database):
    elasticapm_client.begin_transaction("transaction.test")
    requests = [
        pymongo.InsertOne({"x": 1}),
        pymongo.DeleteOne({"x": 1}),
        pymongo.ReplaceOne({"w": 1}, {"z": 1}, upsert=True),
    ]
    result = mongo_database.blogposts.bulk_write(requests)
    assert result.inserted_count == 1
    assert result.deleted_count == 1
    assert result.upserted_count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.bulk_write"


@pytest.mark.integrationtest
def test_collection_count(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    count = mongo_database.blogposts.count()
    assert count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.count"
    assert span["context"]["destination"] == {
        "address": os.environ.get("MONGODB_HOST", "localhost"),
        "port": int(os.environ.get("MONGODB_PORT", 27017)),
        "service": {"name": "mongodb", "resource": "mongodb", "type": "db"},
    }


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_delete_one(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.delete_one({"author": "Tom"})
    assert r.deleted_count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.delete_one"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_delete_many(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.delete_many({"author": "Tom"})
    assert r.deleted_count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.delete_many"


@pytest.mark.integrationtest
def test_collection_insert(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.insert(blogpost)
    assert r is not None
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.insert"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_insert_one(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.insert_one(blogpost)
    assert r.inserted_id is not None
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.insert_one"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_insert_many(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.insert_many([blogpost])
    assert len(r.inserted_ids) == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]

    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.insert_many"


@pytest.mark.integrationtest
def test_collection_find(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    blogposts = []
    for i in range(1000):
        blogposts.append({"author": "Tom", "comments": i})
    mongo_database.blogposts.insert(blogposts)
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.events[TRANSACTION]
    elasticapm_client.begin_transaction("transaction.test")
    r = list(mongo_database.blogposts.find({"comments": {"$gt": 995}}))

    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.cursor.refresh"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_find_one(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert_one(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.find_one({"author": "Tom"})
    assert r["author"] == "Tom"
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.find_one"


@pytest.mark.integrationtest
def test_collection_remove(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.remove({"author": "Tom"})
    assert r["n"] == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.remove"


@pytest.mark.integrationtest
def test_collection_update(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.update({"author": "Tom"}, {"$set": {"author": "Jerry"}})
    assert r["n"] == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.update"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_update_one(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.update_one({"author": "Tom"}, {"$set": {"author": "Jerry"}})
    assert r.modified_count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.update_one"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (3, 0), reason="New in 3.0")
def test_collection_update_many(instrument, elasticapm_client, mongo_database):
    blogpost = {"author": "Tom", "text": "Foo", "date": datetime.datetime.utcnow()}
    r = mongo_database.blogposts.insert(blogpost)
    elasticapm_client.begin_transaction("transaction.test")
    r = mongo_database.blogposts.update_many({"author": "Tom"}, {"$set": {"author": "Jerry"}})
    assert r.modified_count == 1
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.blogposts.update_many"


@pytest.mark.integrationtest
@pytest.mark.skipif(pymongo.version_tuple < (2, 7), reason="New in 2.7")
def test_bulk_execute(instrument, elasticapm_client, mongo_database):
    elasticapm_client.begin_transaction("transaction.test")
    bulk = mongo_database.test_bulk.initialize_ordered_bulk_op()
    bulk.insert({"x": "y"})
    bulk.insert({"z": "x"})
    bulk.find({"x": "y"}).replace_one({"x": "z"})
    bulk.execute()
    elasticapm_client.end_transaction("transaction.test")
    transactions = elasticapm_client.events[TRANSACTION]
    span = _get_pymongo_span(elasticapm_client.spans_for_transaction(transactions[0]))
    assert span["type"] == "db"
    assert span["subtype"] == "mongodb"
    assert span["action"] == "query"
    assert span["name"] == "elasticapm_test.test_bulk.bulk.execute"


def _get_pymongo_span(spans):
    for span in spans:
        if span["subtype"] == "mongodb":
            return span
