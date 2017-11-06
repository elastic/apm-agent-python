# -*- coding: utf-8 -*-
import os

import pytest

from elasticapm.instrumentation import control
from elasticapm.instrumentation.packages.psycopg2 import (PGCursorProxy,
                                                          extract_signature)

try:
    import psycopg2
    has_psycopg2 = True
except ImportError:
    has_psycopg2 = False

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
    sql = """INSERT INTO mytable (id, name) VALUE ('2323', 'Ron')"""
    actual = extract_signature(sql)

    assert "INSERT INTO mytable" == actual


def test_update_with_quotes():
    sql = """UPDATE "my table" set name='Ron' WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "UPDATE my table" == actual


def test_update():
    sql = """update mytable set name = 'Ron where id = 'a'"""
    actual = extract_signature(sql)

    assert "UPDATE mytable" == actual


def test_delete_simple():
    sql = 'DELETE FROM "mytable"'
    actual = extract_signature(sql)

    assert "DELETE FROM mytable" == actual


def test_delete():
    sql = """DELETE FROM "my table" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "DELETE FROM my table" == actual


def test_select_simple():
    sql = """SELECT id, name FROM my_table WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM my_table" == actual


def test_select_with_entity_quotes():
    sql = """SELECT id, name FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_values():
    sql = """SELECT id, 'some name' + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_dollar_quotes():
    sql = """SELECT id, $$some single doubles ' $$ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_invalid_dollar_quotes():
    sql = """SELECT id, $fish$some single doubles ' $$ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM" == actual


def test_select_with_dollar_quotes_custom_token():
    sql = """SELECT id, $token $FROM $ FROM $ FROM single doubles ' $token $ + '" from Denmark' FROM "mytable" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_table_name():
    sql = "SELECT id FROM \"myta\n-æøåble\" WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM myta\n-æøåble" == actual


def test_select_subselect():
    sql = """SELECT id, name FROM (
            SELECT id, 'not a FROM ''value' FROM mytable WHERE id = 2323
    ) LIMIT 20"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_subselect_with_alias():
    sql = """
    SELECT count(*)
    FROM (
        SELECT count(id) AS some_alias, some_column
        FROM mytable
        GROUP BY some_colun
        HAVING count(id) > 1
    ) AS foo
    """
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_multiple_tables():
    sql = """SELECT count(table2.id)
        FROM table1, table2, table2
        WHERE table2.id = table1.table2_id
    """
    actual = extract_signature(sql)
    assert "SELECT FROM table1" == actual


def test_select_with_invalid_subselect():
    sql = "SELECT id FROM (SELECT * """
    actual = extract_signature(sql)

    assert "SELECT FROM" == actual


def test_select_with_invalid_literal():
    sql = "SELECT 'neverending literal FROM (SELECT * FROM ..."""
    actual = extract_signature(sql)

    assert "SELECT FROM" == actual


def test_savepoint():
    sql = """SAVEPOINT x_asd1234"""
    actual = extract_signature(sql)

    assert "SAVEPOINT" == actual


def test_begin():
    sql = """BEGIN"""
    actual = extract_signature(sql)

    assert "BEGIN" == actual


def test_create_index_with_name():
    sql = """CREATE INDEX myindex ON mytable"""
    actual = extract_signature(sql)

    assert "CREATE INDEX" == actual


def test_create_index_without_name():
    sql = """CREATE INDEX ON mytable"""
    actual = extract_signature(sql)

    assert "CREATE INDEX" == actual


def test_drop_table():
    sql = """DROP TABLE mytable"""
    actual = extract_signature(sql)

    assert "DROP TABLE" == actual


def test_multi_statement_sql():
    sql = """CREATE TABLE mytable; SELECT * FROM mytable; DROP TABLE mytable"""
    actual = extract_signature(sql)

    assert "CREATE TABLE" == actual

@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_register_type(postgres_connection, elasticapm_client):
    import psycopg2.extras

    control.instrument()

    try:
        elasticapm_client.begin_transaction("web.django")
        new_type = psycopg2.extras.register_uuid(None, postgres_connection)
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the traces for the other tests.
        elasticapm_client.instrumentation_store.get_all()

    assert new_type is not None


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_register_json(postgres_connection, elasticapm_client):
    # register_json bypasses register_type, so we have to test unwrapping
    # separately
    import psycopg2.extras

    control.instrument()

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
def test_psycopg2_tracing_outside_of_elasticapm_transaction(postgres_connection, elasticapm_client):
    control.instrument()
    cursor = postgres_connection.cursor()
    # check that the cursor is a proxy, even though we're not in an elasticapm
    # transaction
    assert isinstance(cursor, PGCursorProxy)
    cursor.execute('SELECT 1')
    transactions = elasticapm_client.instrumentation_store.get_all()
    assert transactions == []


@pytest.mark.integrationtest
@pytest.mark.skipif(not has_postgres_configured, reason="PostgresSQL not configured")
def test_psycopg2_select_LIKE(postgres_connection, elasticapm_client):
    """
    Check that we pass queries with %-notation but without parameters
    properly to the dbapi backend
    """
    control.instrument()
    cursor = postgres_connection.cursor()
    query = "SELECT * FROM test WHERE name LIKE 't%'"

    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        cursor.fetchall()
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the traces for the other tests.
        transactions = elasticapm_client.instrumentation_store.get_all()
        traces = transactions[0]['traces']
        trace = traces[0]
        assert trace['name'] == 'SELECT FROM test'
        assert 'db' in trace['context']
        assert trace['context']['db']['type'] == 'sql'
        assert trace['context']['db']['statement'] == query
