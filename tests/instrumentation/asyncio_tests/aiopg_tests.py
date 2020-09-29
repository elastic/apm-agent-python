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

import pytest  # isort:skip

aiopg = pytest.importorskip("aiopg")  # isort:skip

import os

from elasticapm.conf import constants

try:
    from psycopg2 import sql

    has_sql_module = True
except ImportError:
    # as of Jan 2018, psycopg2cffi doesn't have this module
    has_sql_module = False

pytestmark = [pytest.mark.aiopg, pytest.mark.asyncio]

if "POSTGRES_DB" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping aiopg tests, no POSTGRES_DB environment variable set"))


def dsn():
    return "dbname={database} user={user} password={password} host={host} port={port}".format(
        **{
            "database": os.environ.get("POSTGRES_DB", "elasticapm_test"),
            "user": os.environ.get("POSTGRES_USER", "postgres"),
            "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "host": os.environ.get("POSTGRES_HOST", "localhost"),
            "port": os.environ.get("POSTGRES_PORT", "5432"),
        }
    )


@pytest.fixture()
async def cursor(request):
    conn = await aiopg.connect(dsn())
    cur = await conn.cursor()

    # we use a finalizer instead of yield, because Python 3.5 throws a syntax error, even if the test doesn't run
    def rollback():
        cur.raw.execute("ROLLBACK")
        cur.close()
        conn.close()

    request.addfinalizer(rollback)
    await cur.execute(
        "BEGIN;"
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )
    return cur


async def test_select_sleep(instrument, cursor, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    await cursor.execute("SELECT pg_sleep(0.1);")
    elasticapm_client.end_transaction("test", "OK")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert 100 < span["duration"] < 110
    assert transaction["id"] == span["transaction_id"]
    assert span["type"] == "db"
    assert span["subtype"] == "postgres"
    assert span["action"] == "query"
    assert span["sync"] == False


@pytest.mark.skipif(not has_sql_module, reason="SQL module missing from psycopg2")
async def test_composable_queries(instrument, cursor, elasticapm_client):
    query = sql.SQL("SELECT * FROM {table} WHERE {row} LIKE 't%' ORDER BY {row} DESC").format(
        table=sql.Identifier("test"), row=sql.Identifier("name")
    )
    baked_query = query.as_string(cursor.raw)
    elasticapm_client.begin_transaction("test")
    await cursor.execute(query)
    elasticapm_client.end_transaction("test", "OK")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]
    assert span["name"] == "SELECT FROM test"
    assert span["context"]["db"]["statement"] == baked_query


async def test_callproc(instrument, cursor, elasticapm_client):
    await cursor.execute(
        """
        CREATE OR REPLACE FUNCTION squareme(me INT)
        RETURNS INTEGER
        LANGUAGE SQL
        AS $$
            SELECT me*me;
        $$;
        """
    )
    elasticapm_client.begin_transaction("test")
    await cursor.callproc("squareme", [2])
    result = await cursor.fetchall()
    assert result[0][0] == 4
    elasticapm_client.end_transaction("test", "OK")
    transactions = elasticapm_client.events[constants.TRANSACTION]
    span = elasticapm_client.spans_for_transaction(transactions[0])[0]
    assert span["name"] == "squareme()"
    assert span["action"] == "exec"
