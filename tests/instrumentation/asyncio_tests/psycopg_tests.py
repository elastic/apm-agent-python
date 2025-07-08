#  BSD 3-Clause License
#
#  Copyright (c) 2025, Elasticsearch BV
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
import pytest_asyncio

from elasticapm.conf import constants

psycopg = pytest.importorskip("psycopg")  # isort:skip
pytestmark = [pytest.mark.psycopg, pytest.mark.asyncio]

if "POSTGRES_DB" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping psycopg tests, no POSTGRES_DB environment variable set"))


def connect_kwargs():
    return {
        "dbname": os.environ.get("POSTGRES_DB", "elasticapm_test"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "host": os.environ.get("POSTGRES_HOST", None),
        "port": os.environ.get("POSTGRES_PORT", None),
    }


@pytest_asyncio.fixture(scope="function")
async def postgres_connection(request):
    conn = await psycopg.AsyncConnection.connect(**connect_kwargs())
    cursor = conn.cursor()
    await cursor.execute(
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    yield conn

    # cleanup
    await cursor.execute("ROLLBACK")


async def test_cursor_execute_signature(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    record = await cursor.execute(query="SELECT 1", params=None, prepare=None, binary=None)
    assert record


async def test_cursor_executemany_signature(instrument, postgres_connection, elasticapm_client):
    cursor = postgres_connection.cursor()
    res = await cursor.executemany(
        query="INSERT INTO test VALUES (%s, %s)",
        params_seq=((4, "four"),),
        returning=False,
    )
    assert res is None


async def test_execute_with_sleep(instrument, postgres_connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    cursor = postgres_connection.cursor()
    await cursor.execute("SELECT pg_sleep(0.1);")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    assert len(spans) == 1
    span = spans[0]
    assert 100 < span["duration"] < 110
    assert transaction["id"] == span["transaction_id"]
    assert span["type"] == "db"
    assert span["subtype"] == "postgresql"
    assert span["action"] == "query"
    assert span["sync"] == False
    assert span["name"] == "SELECT FROM"


async def test_executemany(instrument, postgres_connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    cursor = postgres_connection.cursor()
    await cursor.executemany("INSERT INTO test VALUES (%s, %s);", [(1, "uno"), (2, "due")])
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    assert len(spans) == 1
    span = spans[0]
    assert transaction["id"] == span["transaction_id"]
    assert span["subtype"] == "postgresql"
    assert span["action"] == "query"
    assert span["sync"] == False
    assert span["name"] == "INSERT INTO test"
