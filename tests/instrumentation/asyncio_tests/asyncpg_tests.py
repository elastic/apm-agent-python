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

from elasticapm.conf import constants

asyncpg = pytest.importorskip("asyncpg")  # isort:skip
pytestmark = [pytest.mark.asyncpg, pytest.mark.asyncio]

if "POSTGRES_DB" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping asyncpg tests, no POSTGRES_DB environment variable set"))


def dsn():
    return "postgres://{user}:{password}@{host}:{port}/{database}".format(
        **{
            "database": os.environ.get("POSTGRES_DB", "elasticapm_test"),
            "user": os.environ.get("POSTGRES_USER", "postgres"),
            "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "host": os.environ.get("POSTGRES_HOST", "localhost"),
            "port": os.environ.get("POSTGRES_PORT", "5432"),
        }
    )


@pytest.fixture()
async def connection(request):
    conn = await asyncpg.connect(dsn())

    await conn.execute(
        "BEGIN;"
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )
    yield conn

    await conn.execute("ROLLBACK")
    await conn.close()


async def test_execute_with_sleep(instrument, connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    await connection.execute("SELECT pg_sleep(0.1);")
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


async def test_executemany(instrument, connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    await connection.executemany("INSERT INTO test VALUES ($1, $2);", [(1, "uno"), (2, "due")])
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


def _assert_fetch(result):
    assert len(result) == 3
    assert all(isinstance(val, asyncpg.Record) for val in result)


def _assert_fetchval(result):
    assert result == 1


def _assert_fetchrow(result):
    assert isinstance(result, asyncpg.Record)
    assert result["id"] == 1


@pytest.mark.usefixtures("instrument")
@pytest.mark.parametrize(
    "method,verify", [("fetch", _assert_fetch), ("fetchval", _assert_fetchval), ("fetchrow", _assert_fetchrow)]
)
async def test_fetch_methods(connection, elasticapm_client, method, verify):
    elasticapm_client.begin_transaction("test")
    result = await getattr(connection, method)("SELECT id FROM test;")
    elasticapm_client.end_transaction("test", "OK")

    verify(result)

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    assert len(spans) == 1
    span = spans[0]
    assert transaction["id"] == span["transaction_id"]
    assert span["subtype"] == "postgresql"
    assert span["action"] == "query"
    assert span["sync"] is False
    assert span["name"] == "SELECT FROM test"


@pytest.mark.usefixtures("instrument")
async def test_truncate_long_sql(connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    await connection.execute(f"SELECT id, name FROM test WHERE name = '{'x' * 10010}';")
    elasticapm_client.end_transaction("test", "OK")

    transactions = elasticapm_client.events[constants.TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    statement = spans[0]["context"]["db"]["statement"]
    assert len(statement) == 10000
    assert statement.endswith("...")
