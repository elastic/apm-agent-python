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
from elasticapm.instrumentation.packages.psycopg2 import PGCursorProxy, extract_signature, get_destination_info
from elasticapm.utils import default_ports
from tests.fixtures import TempStoreClient

psycopg2 = pytest.importorskip("psycopg2")


try:
    from psycopg2 import compat

    is_cffi = True
except ImportError:
    is_cffi = False

try:
    import psycopg2.extensions
except ImportError:
    psycopg2.extensions = None


pytestmark = pytest.mark.psycopg2

has_postgres_configured = "POSTGRES_DB" in os.environ


def connect_kwargs():
    return {
        "database": os.environ.get("POSTGRES_DB", "elasticapm_test"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "host": os.environ.get("POSTGRES_HOST", None),
        "port": os.environ.get("POSTGRES_PORT", None),
    }


@pytest.fixture(scope="function")
def postgres_connection(request):
    conn = psycopg2.connect(**connect_kwargs())
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    cursor.execute("ROLLBACK")


def test_insert():
    sql_statement = """INSERT INTO mytable (id, name) VALUE ('2323', 'Ron')"""
    actual = extract_signature(sql_statement)

    assert "INSERT INTO mytable" == actual


def test_update_with_quotes():
    sql_statement = """UPDATE "my table" set name='Ron' WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "UPDATE my table" == actual


def test_update():
    sql_statement = """update mytable set name = 'Ron where id = 'a'"""
    actual = extract_signature(sql_statement)

    assert "UPDATE mytable" == actual


def test_delete_simple():
    sql_statement = 'DELETE FROM "mytable"'
    actual = extract_signature(sql_statement)

    assert "DELETE FROM mytable" == actual


def test_delete():
    sql_statement = """DELETE FROM "my table" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "DELETE FROM my table" == actual


def test_select_simple():
    sql_statement = """SELECT id, name FROM my_table WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM my_table" == actual


def test_select_with_entity_quotes():
    sql_statement = """SELECT id, name FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_values():
    sql_statement = """SELECT id, 'some name' + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_with_dollar_quotes():
    sql_statement = """SELECT id, $$some single doubles ' $$ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_with_invalid_dollar_quotes():
    sql_statement = """SELECT id, $fish$some single doubles ' $$ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM" == actual


def test_select_with_dollar_quotes_custom_token():
    sql_statement = """SELECT id, $token $FROM $ FROM $ FROM single doubles ' $token $ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_table_name():
    sql_statement = """SELECT id FROM "myta\n-æøåble" WHERE id = 2323"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM myta\n-æøåble" == actual


def test_select_subselect():
    sql_statement = """SELECT id, name FROM (
            SELECT id, 'not a FROM ''value' FROM mytable WHERE id = 2323
    ) LIMIT 20"""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_subselect_with_alias():
    sql_statement = """
    SELECT count(*)
    FROM (
        SELECT count(id) AS some_alias, some_column
        FROM mytable
        GROUP BY some_colun
        HAVING count(id) > 1
    ) AS foo
    """
    actual = extract_signature(sql_statement)

    assert "SELECT FROM mytable" == actual


def test_select_with_multiple_tables():
    sql_statement = """SELECT count(table2.id)
        FROM table1, table2, table2
        WHERE table2.id = table1.table2_id
    """
    actual = extract_signature(sql_statement)
    assert "SELECT FROM table1" == actual


def test_select_with_invalid_subselect():
    sql_statement = "SELECT id FROM (SELECT * " ""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM" == actual


def test_select_with_invalid_literal():
    sql_statement = "SELECT 'neverending literal FROM (SELECT * FROM ..." ""
    actual = extract_signature(sql_statement)

    assert "SELECT FROM" == actual


def test_savepoint():
    sql_statement = """SAVEPOINT x_asd1234"""
    actual = extract_signature(sql_statement)

    assert "SAVEPOINT" == actual


def test_begin():
    sql_statement = """BEGIN"""
    actual = extract_signature(sql_statement)

    assert "BEGIN" == actual


def test_create_index_with_name():
    sql_statement = """CREATE INDEX myindex ON mytable"""
    actual = extract_signature(sql_statement)

    assert "CREATE INDEX" == actual


def test_create_index_without_name():
    sql_statement = """CREATE INDEX ON mytable"""
    actual = extract_signature(sql_statement)

    assert "CREATE INDEX" == actual


def test_drop_table():
    sql_statement = """DROP TABLE mytable"""
    actual = extract_signature(sql_statement)

    assert "DROP TABLE" == actual


def test_multi_statement_sql():
    sql_statement = """CREATE TABLE mytable; SELECT * FROM mytable; DROP TABLE mytable"""
    actual = extract_signature(sql_statement)

    assert "CREATE TABLE" == actual


def test_fully_qualified_table_name():
    sql_statement = """SELECT a.b FROM db.schema.mytable as a;"""
    actual = extract_signature(sql_statement)
    assert "SELECT FROM db.schema.mytable" == actual


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
def test_psycopg2_register_type(instrument, postgres_connection, elasticapm_client):
    import psycopg2.extras

    elasticapm_client.begin_transaction("web.django")
    new_type = psycopg2.extras.register_uuid(None, postgres_connection)
    elasticapm_client.end_transaction(None, "test-transaction")

    assert new_type is not None


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_register_json(instrument, postgres_connection, elasticapm_client):
    # register_json bypasses register_type, so we have to test unwrapping
    # separately
    import psycopg2.extras

    elasticapm_client.begin_transaction("web.django")
    # as arg
    new_type = psycopg2.extras.register_json(postgres_connection, loads=lambda x: x)
    assert new_type is not None
    # as kwarg
    new_type = psycopg2.extras.register_json(conn_or_curs=postgres_connection, loads=lambda x: x)
    assert new_type is not None
    elasticapm_client.end_transaction(None, "test-transaction")


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
@pytest.mark.skipif(
    not hasattr(psycopg2.extensions, "quote_ident"), reason="psycopg2 driver doesn't have quote_ident extension"
)
def test_psycopg2_quote_ident(instrument, postgres_connection, elasticapm_client):
    elasticapm_client.begin_transaction("web.django")
    ident = psycopg2.extensions.quote_ident("x'x", postgres_connection)
    elasticapm_client.end_transaction(None, "test-transaction")

    assert ident == '"x\'x"'


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
@pytest.mark.skipif(
    not hasattr(psycopg2.extensions, "encrypt_password"),
    reason="psycopg2 driver doesn't have encrypt_password extension",
)
@pytest.mark.skipif(
    hasattr(psycopg2, "__libpq_version__") and psycopg2.__libpq_version__ < 100000,
    reason="test code requires libpq >= 10",
)
def test_psycopg2_encrypt_password(instrument, postgres_connection, elasticapm_client):
    elasticapm_client.begin_transaction("web.django")
    pw1 = psycopg2.extensions.encrypt_password("user", "password", postgres_connection)
    pw2 = psycopg2.extensions.encrypt_password("user", "password", postgres_connection, None)
    pw3 = psycopg2.extensions.encrypt_password("user", "password", postgres_connection, algorithm=None)
    pw4 = psycopg2.extensions.encrypt_password("user", "password", scope=postgres_connection, algorithm=None)
    elasticapm_client.end_transaction(None, "test-transaction")

    assert pw1.startswith("md5") and (pw1 == pw2 == pw3 == pw4)


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_tracing_outside_of_elasticapm_transaction(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    # check that the cursor is a proxy, even though we're not in an elasticapm
    # transaction
    assert isinstance(cursor, PGCursorProxy)
    cursor.execute("SELECT 1")
    transactions = elasticapm_client.events[TRANSACTION]
    assert not transactions


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_select_LIKE(instrument, postgres_connection, elasticapm_client):
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
@pytest.mark.skipif(is_cffi, reason="psycopg2cffi does not have the sql module")
def test_psycopg2_composable_query_works(instrument, postgres_connection, elasticapm_client):
    """
    Check that we parse queries that are psycopg2.sql.Composable correctly
    """
    from psycopg2 import sql

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
def test_psycopg2_call_stored_procedure(instrument, postgres_connection, elasticapm_client):
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
    cursor.callproc("squareme", [2])
    result = cursor.fetchall()
    assert result[0][0] == 4
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]
    assert span["name"] == "squareme()"
    assert span["action"] == "exec"


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg_context_manager(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with psycopg2.connect(**connect_kwargs()) as conn:
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
def test_psycopg2_rows_affected(instrument, postgres_connection, elasticapm_client):
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
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
@pytest.mark.skipif(is_cffi, reason="psycopg2cffi doesn't have execute_values")
def test_psycopg2_execute_values(instrument, postgres_connection, elasticapm_client):
    from psycopg2.extras import execute_values

    cursor = postgres_connection.cursor()
    try:
        elasticapm_client.begin_transaction("web.django")
        query = "INSERT INTO test VALUES %s"
        data = tuple((i, "xxxxx") for i in range(999))
        # this creates a long (~14000 characters) query, encoded as byte string.
        # This tests that we shorten already-encoded strings.
        execute_values(cursor, query, data, page_size=1000)
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        assert spans[0]["name"] == "INSERT INTO test"
        assert len(spans[0]["context"]["db"]["statement"]) == 10000, spans[0]["context"]["db"]["statement"]


@pytest.mark.integrationtest
def test_psycopg2_connection(instrument, elasticapm_transaction, postgres_connection):
    # elastciapm_client.events is only available on `TempStoreClient`, this keeps the type checkers happy
    elasticapm_client = cast(TempStoreClient, get_client())
    elasticapm_client.end_transaction("test", "success")
    span = elasticapm_client.events[SPAN][0]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    assert span["name"] == f"psycopg2.connect {host}:5432"
    assert span["action"] == "connect"


@pytest.mark.parametrize(
    "host_in,port_in,expected_host_out,expected_port_out",
    (
        (None, None, "localhost", 5432),
        (None, 5432, "localhost", 5432),
        ("localhost", "5432", "localhost", 5432),
        ("foo.bar", "5432", "foo.bar", 5432),
        ("localhost,foo.bar", "5432,1234", "localhost", 5432),  # multiple hosts
    ),
)
def test_get_destination(host_in, port_in, expected_host_out, expected_port_out):
    host, port = get_destination_info(host_in, port_in)
    assert host == expected_host_out
    assert port == expected_port_out
