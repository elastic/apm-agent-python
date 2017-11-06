import sqlite3


def test_connect(elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE testdb (id integer, username text)""")
    cursor.execute("""INSERT INTO testdb VALUES (1, "Ron")""")
    cursor.execute("""DROP TABLE testdb""")

    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'sqlite3.connect :memory:',
                           'CREATE TABLE', 'INSERT INTO testdb',
                           'DROP TABLE'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'sqlite3.connect :memory:'
    assert traces[0]['type'] == 'db.sqlite.connect'

    assert traces[1]['name'] == 'CREATE TABLE'
    assert traces[1]['type'] == 'db.sqlite.sql'

    assert traces[2]['name'] == 'INSERT INTO testdb'
    assert traces[2]['type'] == 'db.sqlite.sql'

    assert traces[3]['name'] == 'DROP TABLE'
    assert traces[3]['type'] == 'db.sqlite.sql'

    assert len(traces) == 4
