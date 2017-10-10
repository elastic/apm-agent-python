# -*- coding: utf-8 -*-
from elasticapm.instrumentation.packages.mysql import extract_signature


def test_insert():
    sql = """INSERT INTO `mytable` (id, name) VALUE ('2323', 'Ron')"""
    actual = extract_signature(sql)

    assert "INSERT INTO mytable" == actual


def test_update():
    sql = """UPDATE `mytable` set name='Ron' WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "UPDATE mytable" == actual


def test_delete():
    sql = """DELETE FROM `mytable` WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "DELETE FROM mytable" == actual


def test_select_simple():
    sql = """SELECT `id`, `name` FROM `mytable` WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_entity_quotes():
    sql = """SELECT `id`, `name` FROM `mytable` WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_values():
    sql = """SELECT id, 'some \\'name' + " from Denmark" FROM `mytable` WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM mytable" == actual


def test_select_with_difficult_table_name():
    sql = "SELECT id FROM `myta\n-æøåble` WHERE id = 2323"""
    actual = extract_signature(sql)

    assert "SELECT FROM myta\n-æøåble" == actual


def test_select_subselect():
    sql = """SELECT id, name FROM (
            SELECT id, "not a FROM ''value" FROM mytable WHERE id = 2323
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


def test_select_with_invalid_literal():
    sql = "SELECT \"neverending literal FROM (SELECT * FROM ..."""
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
