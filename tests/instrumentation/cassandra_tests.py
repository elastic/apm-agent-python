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

pytest.importorskip("cassandra")  # isort:skip

import os

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement

from elasticapm.conf.constants import TRANSACTION
from elasticapm.instrumentation.packages.dbapi2 import extract_signature

pytestmark = pytest.mark.cassandra


@pytest.fixture()
def cassandra_cluster():
    cluster = Cluster([os.environ.get("CASSANDRA_HOST", "localhost")])
    yield cluster
    del cluster


@pytest.fixture()
def cassandra_session(cassandra_cluster):
    session = cassandra_cluster.connect()
    session.execute(
        """
        CREATE KEYSPACE testkeyspace
        WITH REPLICATION = { 'class' : 'SimpleStrategy' ,'replication_factor' : 1 }
    """
    )
    session.execute("USE testkeyspace;")
    session.execute("CREATE TABLE testkeyspace.users ( id UUID PRIMARY KEY, name text);")
    yield session
    session.execute("DROP KEYSPACE testkeyspace;")


def test_cassandra_connect(instrument, elasticapm_client, cassandra_cluster):
    elasticapm_client.begin_transaction("transaction.test")
    sess = cassandra_cluster.connect()
    elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]

    assert span["type"] == "db"
    assert span["subtype"] == "cassandra"
    assert span["action"] == "connect"
    assert span["duration"] > 0
    assert span["name"] == "Cluster.connect"


def test_select_query_string(instrument, cassandra_session, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    cassandra_session.execute("SELECT name from users")
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["type"] == "db"
    assert span["subtype"] == "cassandra"
    assert span["action"] == "query"
    assert span["name"] == "SELECT FROM users"
    assert span["context"] == {"db": {"statement": "SELECT name from users", "type": "sql"}}


def test_select_simple_statement(instrument, cassandra_session, elasticapm_client):
    statement = SimpleStatement("SELECT name from users")
    elasticapm_client.begin_transaction("transaction.test")
    cassandra_session.execute(statement)
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["type"] == "db"
    assert span["subtype"] == "cassandra"
    assert span["action"] == "query"
    assert span["name"] == "SELECT FROM users"
    assert span["context"] == {"db": {"statement": "SELECT name from users", "type": "sql"}}


def test_select_prepared_statement(instrument, cassandra_session, elasticapm_client):
    prepared_statement = cassandra_session.prepare("SELECT name from users")
    elasticapm_client.begin_transaction("transaction.test")
    cassandra_session.execute(prepared_statement)
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["type"] == "db"
    assert span["subtype"] == "cassandra"
    assert span["action"] == "query"
    assert span["name"] == "SELECT FROM users"
    assert span["context"] == {"db": {"statement": "SELECT name from users", "type": "sql"}}


def test_signature_create_keyspace():
    assert (
        extract_signature(
            "CREATE KEYSPACE testkeyspace WITH REPLICATION = { 'class' : 'NetworkTopologyStrategy', 'datacenter1' : 3 };"
        )
        == "CREATE KEYSPACE"
    )


def test_signature_create_columnfamily():
    assert (
        extract_signature(
            """CREATE COLUMNFAMILY users (
  userid text PRIMARY KEY,
  first_name text,
  last_name text,
  emails set<text>,
  top_scores list<int>,
  todo map<timestamp, text>
);"""
        )
        == "CREATE COLUMNFAMILY"
    )


def test_select_from_collection():
    assert extract_signature("SELECT first, last FROM a.b WHERE id = 1;") == "SELECT FROM a.b"
