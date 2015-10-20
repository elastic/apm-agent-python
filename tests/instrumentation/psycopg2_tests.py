# -*- coding: utf-8 -*-
import os

import pytest

from opbeat.instrumentation import control
from opbeat.instrumentation.packages.psycopg2 import extract_signature
from tests.contrib.django.django_tests import get_client

try:
    import psycopg2
    has_psycopg2 = True
except ImportError:
    has_psycopg2 = False

travis_and_psycopg2 = 'TRAVIS' not in os.environ or not has_psycopg2


def test_insert():
    sql = """INSERT INTO mytable (id, name) VALUE ('2323', 'Ron')"""
    actual = extract_signature(sql)

    assert "INSERT INTO mytable" == actual


def test_update():
    sql = """UPDATE "my table" set name='Ron' WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "UPDATE my table" == actual


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

@pytest.mark.skipif(travis_and_psycopg2,
                    reason="Requires postgres server. Only runs on travisci.")
def test_psycopg2_register_type():
    import psycopg2.extras

    client = get_client()
    control.instrument()

    try:
        client.begin_transaction("web.django")
        conn = psycopg2.connect(database="opbeat_test", user="postgres")
        new_type = psycopg2.extras.register_uuid(None, conn)
        client.end_transaction(None, "test-transaction")
    finally:
        # make sure we've cleared out the traces for the other tests.
        client.instrumentation_store.get_all()

    assert new_type is not None
