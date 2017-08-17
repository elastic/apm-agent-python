import sqlite3

import mock

import elasticapm.instrumentation.control
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentSQLiteTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        elasticapm.instrumentation.control.instrument()

    @mock.patch("elasticapm.traces.TransactionsStore.should_collect")
    def test_connect(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")

        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE testdb (id integer, username text)""")
        cursor.execute("""INSERT INTO testdb VALUES (1, "Ron")""")
        cursor.execute("""DROP TABLE testdb""")

        self.client.end_transaction("MyView")

        transactions = self.client.instrumentation_store.get_all()
        traces = transactions[0]['traces']

        expected_signatures = ['transaction', 'sqlite3.connect :memory:',
                               'CREATE TABLE', 'INSERT INTO testdb',
                               'DROP TABLE']

        self.assertEqual(set([t['name'] for t in traces]),
                         set(expected_signatures))

        self.assertEqual(traces[0]['name'], 'sqlite3.connect :memory:')
        self.assertEqual(traces[0]['type'], 'db.sqlite.connect')

        self.assertEqual(traces[1]['name'], 'CREATE TABLE')
        self.assertEqual(traces[1]['type'], 'db.sqlite.sql')

        self.assertEqual(traces[2]['name'], 'INSERT INTO testdb')
        self.assertEqual(traces[2]['type'], 'db.sqlite.sql')

        self.assertEqual(traces[3]['name'], 'DROP TABLE')
        self.assertEqual(traces[3]['type'], 'db.sqlite.sql')

        self.assertEqual(traces[4]['name'], 'transaction')
        self.assertEqual(traces[4]['type'], 'transaction')

        self.assertEqual(len(traces), 5)
