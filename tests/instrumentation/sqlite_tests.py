import sqlite3


def test_connect(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE testdb (id integer, username text)""")
    cursor.execute("""INSERT INTO testdb VALUES (1, "Ron")""")
    cursor.execute("""DROP TABLE testdb""")

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    spans = transactions[0]['spans']

    expected_signatures = {'sqlite3.connect :memory:',
                           'CREATE TABLE', 'INSERT INTO testdb',
                           'DROP TABLE'}

    assert {t['name'] for t in spans} == expected_signatures

    assert spans[0]['name'] == 'sqlite3.connect :memory:'
    assert spans[0]['type'] == 'db.sqlite.connect'

    assert spans[1]['name'] == 'CREATE TABLE'
    assert spans[1]['type'] == 'db.sqlite.sql'

    assert spans[2]['name'] == 'INSERT INTO testdb'
    assert spans[2]['type'] == 'db.sqlite.sql'

    assert spans[3]['name'] == 'DROP TABLE'
    assert spans[3]['type'] == 'db.sqlite.sql'

    assert len(spans) == 4
