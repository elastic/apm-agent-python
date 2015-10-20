# -*- coding: utf-8 -*-
from opbeat.instrumentation.packages.mysql import extract_signature
from tests.utils.compat import TestCase


class ExtractSignatureTest(TestCase):
    def test_insert(self):
        sql = """INSERT INTO `mytable` (id, name) VALUE ('2323', 'Ron')"""
        actual = extract_signature(sql)

        self.assertEqual("INSERT INTO mytable", actual)

    def test_update(self):
        sql = """UPDATE `mytable` set name='Ron' WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("UPDATE mytable", actual)

    def test_delete(self):
        sql = """DELETE FROM `mytable` WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("DELETE FROM mytable", actual)

    def test_select_simple(self):
        sql = """SELECT `id`, `name` FROM `mytable` WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM mytable", actual)

    def test_select_with_entity_quotes(self):
        sql = """SELECT `id`, `name` FROM `mytable` WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM mytable", actual)

    def test_select_with_difficult_values(self):
        sql = """SELECT id, 'some \\'name' + " from Denmark" FROM `mytable` WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM mytable", actual)

    def test_select_with_difficult_table_name(self):
        sql = "SELECT id FROM `myta\n-æøåble` WHERE id = 2323"""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM myta\n-æøåble", actual)

    def test_select_subselect(self):
        sql = """SELECT id, name FROM (
                SELECT id, "not a FROM ''value" FROM mytable WHERE id = 2323
        ) LIMIT 20"""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM mytable", actual)

    def test_select_subselect_with_alias(self):
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

        self.assertEqual("SELECT FROM mytable", actual)

    def test_select_with_multiple_tables(self):
        sql = """SELECT count(table2.id)
            FROM table1, table2, table2
            WHERE table2.id = table1.table2_id
        """
        actual = extract_signature(sql)
        self.assertEqual("SELECT FROM table1", actual)

    def test_select_with_invalid_literal(self):
        sql = "SELECT \"neverending literal FROM (SELECT * FROM ..."""
        actual = extract_signature(sql)

        self.assertEqual("SELECT FROM", actual)

    def test_savepoint(self):
        sql = """SAVEPOINT x_asd1234"""
        actual = extract_signature(sql)

        self.assertEqual("SAVEPOINT", actual)

    def test_begin(self):
        sql = """BEGIN"""
        actual = extract_signature(sql)

        self.assertEqual("BEGIN", actual)

    def test_create_index_with_name(self):
        sql = """CREATE INDEX myindex ON mytable"""
        actual = extract_signature(sql)

        self.assertEqual("CREATE INDEX", actual)

    def test_create_index_without_name(self):
        sql = """CREATE INDEX ON mytable"""
        actual = extract_signature(sql)

        self.assertEqual("CREATE INDEX", actual)

    def test_drop_table(self):
        sql = """DROP TABLE mytable"""
        actual = extract_signature(sql)

        self.assertEqual("DROP TABLE", actual)

    def test_multi_statement_sql(self):
        sql = """CREATE TABLE mytable; SELECT * FROM mytable; DROP TABLE mytable"""
        actual = extract_signature(sql)

        self.assertEqual("CREATE TABLE", actual)
