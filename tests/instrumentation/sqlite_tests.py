import sqlite3

from elasticapm.conf.constants import TRANSACTION


def test_connect(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")

    sqlite3.connect(":memory:")
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    assert spans[0]["name"] == "sqlite3.connect :memory:"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "sqlite"
    assert spans[0]["action"] == "connect"


def test_cursor(instrument, elasticapm_client):
    conn = sqlite3.connect(":memory:")

    elasticapm_client.begin_transaction("transaction.test")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE testdb (id integer, username text)")
    cursor.execute('INSERT INTO testdb VALUES (1, "Ron")')
    cursor.executemany("INSERT INTO testdb VALUES (?, ?)", ((2, "Rasmus"), (3, "Shay")))
    cursor.execute("DROP TABLE testdb")
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    expected_signatures = {"CREATE TABLE", "INSERT INTO testdb", "DROP TABLE"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "CREATE TABLE"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "sqlite"
    assert spans[0]["action"] == "query"

    assert spans[1]["name"] == "INSERT INTO testdb"
    assert spans[1]["type"] == "db"
    assert spans[1]["subtype"] == "sqlite"
    assert spans[1]["action"] == "query"

    assert spans[2]["name"] == "INSERT INTO testdb"
    assert spans[2]["type"] == "db"
    assert spans[2]["subtype"] == "sqlite"
    assert spans[2]["action"] == "query"

    assert spans[3]["name"] == "DROP TABLE"
    assert spans[3]["type"] == "db"
    assert spans[3]["subtype"] == "sqlite"
    assert spans[3]["action"] == "query"

    assert len(spans) == 4


def test_nonstandard_connection_execute(instrument, elasticapm_client):
    conn = sqlite3.connect(":memory:")

    elasticapm_client.begin_transaction("transaction.test")
    conn.execute("CREATE TABLE testdb (id integer, username text)")
    conn.execute('INSERT INTO testdb VALUES (1, "Ron")')
    conn.executemany("INSERT INTO testdb VALUES (?, ?)", ((2, "Rasmus"), (3, "Shay")))
    conn.execute("DROP TABLE testdb")
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])
    expected_signatures = {"CREATE TABLE", "INSERT INTO testdb", "DROP TABLE"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "CREATE TABLE"
    assert spans[0]["type"] == "db"
    assert spans[0]["subtype"] == "sqlite"
    assert spans[0]["action"] == "query"

    assert spans[1]["name"] == "INSERT INTO testdb"
    assert spans[1]["type"] == "db"
    assert spans[1]["subtype"] == "sqlite"
    assert spans[1]["action"] == "query"

    assert spans[2]["name"] == "INSERT INTO testdb"
    assert spans[2]["type"] == "db"
    assert spans[2]["subtype"] == "sqlite"
    assert spans[2]["action"] == "query"

    assert spans[3]["name"] == "DROP TABLE"
    assert spans[3]["type"] == "db"
    assert spans[3]["subtype"] == "sqlite"
    assert spans[3]["action"] == "query"

    assert len(spans) == 4
