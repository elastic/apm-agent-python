import os

import pytest

pyodbc = pytest.importorskip("pyodbc")

pytestmark = pytest.mark.pyodbc


@pytest.yield_fixture(scope="function")
def pyodbc_postgres_connection(request):
    conn_str = ("DRIVER={PostgreSQL Unicode};" "DATABASE=%s;" "UID=%s;" "SERVER=%s;" "PORT=%s;") % (
        os.environ.get("POSTGRES_DB", "elasticapm_test"),
        os.environ.get("POSTGRES_USER", "postgres"),
        os.environ.get("POSTGRES_HOST", None),
        os.environ.get("POSTGRES_PORT", None),
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    cursor.execute("ROLLBACK")


@pytest.mark.integrationtest
def test_pyodbc_select(instrument, pyodbc_postgres_connection, elasticapm_client):
    cursor = pyodbc_postgres_connection.cursor()
    query = "SELECT * FROM test WHERE name LIKE 't%'"

    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        cursor.fetchall()
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        transactions = elasticapm_client.transaction_store.get_all()
        spans = transactions[0]["spans"]
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert "db" in span["context"]
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == query
