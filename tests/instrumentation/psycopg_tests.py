# -*- coding: utf-8 -*-

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

import os
from typing import cast

import pytest

from elasticapm import get_client
from elasticapm.conf.constants import SPAN, TRANSACTION
from elasticapm.instrumentation.packages.psycopg import PGCursorProxy
from elasticapm.utils import default_ports
from tests.fixtures import TempStoreClient

psycopg = pytest.importorskip("psycopg")

pytestmark = pytest.mark.psycopg

has_postgres_configured = "POSTGRES_DB" in os.environ


def connect_kwargs():
    return {
        "dbname": os.environ.get("POSTGRES_DB", "elasticapm_test"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "host": os.environ.get("POSTGRES_HOST", None),
        "port": os.environ.get("POSTGRES_PORT", None),
    }


@pytest.fixture(scope="function")
def postgres_connection(request):
    conn = psycopg.connect(**connect_kwargs())
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    cursor.execute("ROLLBACK")


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_destination(instrument, postgres_connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    cursor = postgres_connection.cursor()
    cursor.execute("SELECT 1")
    elasticapm_client.end_transaction("test")
    transaction = elasticapm_client.events[TRANSACTION][0]
    span = elasticapm_client.spans_for_transaction(transaction)[0]
    assert span["context"]["destination"] == {
        "address": os.environ.get("POSTGRES_HOST", None),
        "port": default_ports["postgresql"],
        "service": {"name": "", "resource": "postgresql/elasticapm_test", "type": ""},
    }


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_tracing_outside_of_elasticapm_transaction(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    # check that the cursor is a proxy, even though we're not in an elasticapm
    # transaction
    assert isinstance(cursor, PGCursorProxy)
    cursor.execute("SELECT 1")
    transactions = elasticapm_client.events[TRANSACTION]
    assert not transactions


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_select_LIKE(instrument, postgres_connection, elasticapm_client):
    """
    Check that we pass queries with %-notation but without parameters
    properly to the dbapi backend
    """
    cursor = postgres_connection.cursor()
    query = "SELECT * FROM test WHERE name LIKE 't%'"

    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        cursor.fetchall()
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the spans for the other tests.
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert span["type"] == "db"
        assert span["subtype"] == "postgresql"
        assert span["action"] == "query"
        assert "db" in span["context"]
        assert span["context"]["db"]["instance"] == "elasticapm_test"
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == query
        assert span["context"]["service"]["target"]["type"] == "postgresql"
        assert span["context"]["service"]["target"]["name"] == "elasticapm_test"


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_composable_query_works(instrument, postgres_connection, elasticapm_client):
    """
    Check that we parse queries that are psycopg.sql.Composable correctly
    """
    from psycopg import sql

    cursor = postgres_connection.cursor()
    query = sql.SQL("SELECT * FROM {table} WHERE {row} LIKE 't%' ORDER BY {row} DESC").format(
        table=sql.Identifier("test"), row=sql.Identifier("name")
    )
    baked_query = query.as_string(cursor.__wrapped__)
    result = None
    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        result = cursor.fetchall()
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the spans for the other tests.
        assert [(2, "two"), (3, "three")] == result
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert "db" in span["context"]
        assert span["context"]["db"]["instance"] == "elasticapm_test"
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == baked_query


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_binary_query_works(instrument, postgres_connection, elasticapm_client):
    """
    Check that we pass queries with %-notation but without parameters
    properly to the dbapi backend
    """
    cursor = postgres_connection.cursor()
    query = b"SELECT * FROM test WHERE name LIKE 't%'"

    baked_query = query.decode()
    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        result = cursor.fetchall()
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the spans for the other tests.
        assert [(2, "two"), (3, "three")] == result
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert "db" in span["context"]
        assert span["context"]["db"]["instance"] == "elasticapm_test"
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == baked_query


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_call_stored_function(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    cursor.execute(
        """
        CREATE OR REPLACE FUNCTION squareme(me INT)
        RETURNS INTEGER
        LANGUAGE SQL
        AS $$
            SELECT me*me;
        $$;
        """
    )
    elasticapm_client.begin_transaction("test")
    cursor.execute("SELECT squareme(2)")
    result = cursor.fetchall()
    assert result[0][0] == 4
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]
    assert span["name"] == "SELECT FROM"
    assert span["action"] == "query"


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_context_manager(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with psycopg.connect(**connect_kwargs()) as conn:
        with conn.cursor() as curs:
            curs.execute("SELECT 1;")
            curs.fetchall()
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 2
    assert spans[0]["subtype"] == "postgresql"
    assert spans[0]["action"] == "connect"
    assert spans[0]["context"]["service"]["target"]["type"] == "postgresql"
    assert spans[0]["context"]["service"]["target"]["name"] == "elasticapm_test"

    assert spans[1]["subtype"] == "postgresql"
    assert spans[1]["action"] == "query"


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_rows_affected(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute("INSERT INTO test VALUES (4, 'four')")
        cursor.execute("SELECT * FROM test")
        cursor.execute("UPDATE test SET name = 'five' WHERE  id = 4")
        cursor.execute("DELETE FROM test WHERE  id = 4")
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])

        assert spans[0]["name"] == "INSERT INTO test"
        assert spans[0]["context"]["db"]["rows_affected"] == 1

        assert spans[1]["name"] == "SELECT FROM test"
        assert "rows_affected" not in spans[1]["context"]["db"]

        assert spans[2]["name"] == "UPDATE test"
        assert spans[2]["context"]["db"]["rows_affected"] == 1

        assert spans[3]["name"] == "DELETE FROM test"
        assert spans[3]["context"]["db"]["rows_affected"] == 1


@pytest.mark.integrationtest
def test_psycopg_connection(instrument, elasticapm_transaction, postgres_connection):
    # elastciapm_client.events is only available on `TempStoreClient`, this keeps the type checkers happy
    elasticapm_client = cast(TempStoreClient, get_client())
    elasticapm_client.end_transaction("test", "success")
    span = elasticapm_client.events[SPAN][0]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    assert span["name"] == f"psycopg.connect {host}:5432"
    assert span["action"] == "connect"
