#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os

import pytest

from elasticapm.conf.constants import TRANSACTION

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
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert span["type"] == "db"
        assert span["subtype"] == "pymssql"
        assert span["action"] == "query"
        assert "db" in span["context"]
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == query
