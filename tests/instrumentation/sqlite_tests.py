import sqlite3

import mock

import opbeat.instrumentation.control
from tests.helpers import get_tempstoreclient
from tests.utils.compat import TestCase


class InstrumentSQLiteTest(TestCase):
    def setUp(self):
        self.client = get_tempstoreclient()
        opbeat.instrumentation.control.instrument()

    @mock.patch("opbeat.traces.RequestsStore.should_collect")
    def test_connect(self, should_collect):
        should_collect.return_value = False
        self.client.begin_transaction("transaction.test")

        conn = sqlite3.connect("testdb.sql")
        cursor = conn.cursor()

        cursor.execute("""CREATE TABLE testdb (id integer, username text)""")
        cursor.execute("""INSERT INTO testdb VALUES (1, "Ron")""")
        cursor.execute("""DROP TABLE testdb""")

        self.client.end_transaction("MyView")

        transactions, traces = self.client.instrumentation_store.get_all()

        expected_signatures = ['transaction', 'sqlite3.connect testdb.sql',
                               'CREATE TABLE', 'INSERT INTO testdb',
                               'DROP TABLE']

        self.assertEqual(set([t['signature'] for t in traces]),
                         set(expected_signatures))

        # Reorder according to the kinds list so we can just test them
        sig_dict = dict([(t['signature'], t) for t in traces])
        traces = [sig_dict[k] for k in expected_signatures]

        self.assertEqual(traces[0]['signature'], 'transaction')
        self.assertEqual(traces[0]['kind'], 'transaction')
        self.assertEqual(traces[0]['transaction'], 'MyView')

        self.assertEqual(traces[1]['signature'], 'sqlite3.connect testdb.sql')
        self.assertEqual(traces[1]['kind'], 'db.sqlite.connect')
        self.assertEqual(traces[1]['transaction'], 'MyView')

        self.assertEqual(traces[2]['signature'], 'CREATE TABLE')
        self.assertEqual(traces[2]['kind'], 'db.sqlite.sql')
        self.assertEqual(traces[2]['transaction'], 'MyView')

        self.assertEqual(traces[3]['signature'], 'INSERT INTO testdb')
        self.assertEqual(traces[3]['kind'], 'db.sqlite.sql')
        self.assertEqual(traces[3]['transaction'], 'MyView')

        self.assertEqual(traces[4]['signature'], 'DROP TABLE')
        self.assertEqual(traces[4]['kind'], 'db.sqlite.sql')
        self.assertEqual(traces[4]['transaction'], 'MyView')

        self.assertEqual(len(traces), 5)
