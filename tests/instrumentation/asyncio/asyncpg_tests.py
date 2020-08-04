#  BSD 3-Clause License
#
#  Copyright (c) 2020, Elasticsearch BV
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

asyncpg = pytest.importorskip("asyncpg")  # isort:skip

import os

from elasticapm.conf import constants


pytestmark = [pytest.mark.asyncpg, pytest.mark.asyncio]


def dsn():
    return "postgres://{user}:{password}@{host}:{port}/{database}".format(
        database=os.environ.get("POSTGRES_DB") or "elasticapm_test",
        user=os.environ.get("POSTGRES_USER") or "postgres",
        password=os.environ.get("POSTGRES_PASSWORD") or "postgres",
        host=os.environ.get("POSTGRES_HOST") or "localhost",
        port=os.environ.get("POSTGRES_PORT") or "5432",
    )


@pytest.fixture()
async def connection(request):
    conn = await asyncpg.connect(dsn())

    def rollback():
        conn.execute("ROLLBACK")
        conn.close()

    request.addfinalizer(rollback)

    await conn.execute(
        "BEGIN;"
        "CREATE TABLE test(id int, name VARCHAR(5) NOT NULL);"
        "INSERT INTO test VALUES (1, 'one'), (2, 'two'), (3, 'three');"
    )

    return connection


async def test_select_sleep(instrument, connection, elasticapm_client):
    elasticapm_client.begin_transaction("test")
    await connection.execute("SELECT pg_sleep(0.1);")
    elasticapm_client.end_transaction("test")

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)

    assert len(spans) == 1
    span = spans[0]
    assert 100 < span["duration"] < 110
    assert transaction["id"] == span["transaction_id"]
    assert span["subtype"] == "postgres"
    assert span["action"] == "query"
    assert span["sync"] == False
