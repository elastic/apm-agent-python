import os

import pytest

pymssql = pytest.importorskip("pymssql")

pytestmark = pytest.mark.pymssql


@pytest.yield_fixture(scope="function")
def pymssql_connection(request):
    conn = pymssql.connect(
        os.environ.get("MSSQL_HOST", "localhost"),
        os.environ.get("MSSQL_USER", "SA"),
        os.environ.get("MSSQL_PASSWORD", ""),
        os.environ.get("MSSQL_DATABASE", "tempdb"),
    )
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE test(id INT, name NVARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    conn.rollback()


@pytest.mark.integrationtest
def test_pymssql_select(instrument, pymssql_connection, elasticapm_client):
    cursor = pymssql_connection.cursor()
    query = "SELECT * FROM test WHERE name LIKE 't%' ORDER BY id"

    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        assert cursor.fetchall() == [(2, "two"), (3, "three")]
        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        transactions = elasticapm_client.transaction_store.get_all()
        spans = transactions[0]["spans"]
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert "db" in span["context"]
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == query
