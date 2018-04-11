# -*- coding: utf-8 -*-
import pytest  # isort:skip
pytest.importorskip("psycopg2")  # isort:skip

import os

import psycopg2

from elasticapm.instrumentation.packages.psycopg2 import (PGCursorProxy,
                                                          extract_signature)

try:
    from psycopg2 import sql
    has_sql_module = True
except ImportError:
    # as of Jan 2018, psycopg2cffi doesn't have this module
    has_sql_module = False


pytestmark = pytest.mark.psycopg2

has_postgres_configured = 'POSTGRES_DB' in os.environ


@pytest.yield_fixture(scope='function')
def postgres_connection(request):
    conn = psycopg2.connect(
        database=os.environ.get('POSTGRES_DB', 'elasticapm_test'),
        user=os.environ.get('POSTGRES_USER', 'postgres'),
        host=os.environ.get('POSTGRES_HOST', None),
        port=os.environ.get('POSTGRES_PORT', None),
    )
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    cursor.execute('ROLLBACK')


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
    sql_statement = "SELECT id FROM \"myta\n-æøåble\" WHERE id = 2323"""
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
    sql_statement = "SELECT id FROM (SELECT * """
    actual = extract_signature(sql_statement)

    assert "SELECT FROM" == actual


def test_select_with_invalid_literal():
    sql_statement = "SELECT 'neverending literal FROM (SELECT * FROM ..."""
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


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_register_type(postgres_connection, elasticapm_client):
    import psycopg2.extras

    try:
        elasticapm_client.begin_transaction("web.django")
        new_type = psycopg2.extras.register_uuid(None, postgres_connection)
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the spans for the other tests.
        elasticapm_client.instrumentation_store.get_all()

    assert new_type is not None


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_register_json(postgres_connection, elasticapm_client):
    # register_json bypasses register_type, so we have to test unwrapping
    # separately
    import psycopg2.extras

    try:
        elasticapm_client.begin_transaction("web.django")
        # as arg
        new_type = psycopg2.extras.register_json(postgres_connection,
                                                 loads=lambda x: x)
        assert new_type is not None
        # as kwarg
        new_type = psycopg2.extras.register_json(conn_or_curs=postgres_connection,
                                                 loads=lambda x: x)
        assert new_type is not None
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the traces for the other tests.
        elasticapm_client.instrumentation_store.get_all()


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_tracing_outside_of_elasticapm_transaction(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    # check that the cursor is a proxy, even though we're not in an elasticapm
    # transaction
    assert isinstance(cursor, PGCursorProxy)
    cursor.execute('SELECT 1')
    transactions = elasticapm_client.instrumentation_store.get_all()
    assert transactions == []


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
        transactions = elasticapm_client.instrumentation_store.get_all()
        spans = transactions[0]['spans']
        span = spans[0]
        assert span['name'] == 'SELECT FROM test'
        assert 'db' in span['context']
        assert span['context']['db']['type'] == 'sql'
        assert span['context']['db']['statement'] == query


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
@pytest.mark.skipif(not has_sql_module, reason="psycopg2.sql module missing")
def test_psycopg2_composable_query_works(instrument, postgres_connection, elasticapm_client):
    """
    Check that we parse queries that are psycopg2.sql.Composable correctly
    """
    cursor = postgres_connection.cursor()
    query = sql.SQL("SELECT * FROM {table} WHERE {row} LIKE 't%' ORDER BY {row} DESC").format(
        table=sql.Identifier('test'),
        row=sql.Identifier('name'),
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
        assert [(2, 'two'), (3, 'three')] == result
        transactions = elasticapm_client.instrumentation_store.get_all()
        spans = transactions[0]['spans']
        span = spans[0]
        assert span['name'] == 'SELECT FROM test'
        assert 'db' in span['context']
        assert span['context']['db']['type'] == 'sql'
        assert span['context']['db']['statement'] == baked_query
