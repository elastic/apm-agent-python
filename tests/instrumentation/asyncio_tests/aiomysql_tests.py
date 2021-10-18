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
from elasticapm.utils import default_ports

aiomysql = pytest.importorskip("aiomysql")

pytestmark = [pytest.mark.asyncio, pytest.mark.aiomysql]


if "MYSQL_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping aiomysql tests, no MYSQL_HOST environment variable set"))


@pytest.fixture(scope="function")
async def aiomysql_connection(request, event_loop):
    assert event_loop.is_running()
    pool = await aiomysql.create_pool(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "eapm"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        db=os.environ.get("MYSQL_DATABASE", "eapm_tests"),
        loop=event_loop,
    )

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("CREATE TABLE `test` (`id` INT, `name` VARCHAR(5))")
                await cursor.execute("INSERT INTO `test` (`id`, `name`) VALUES (1, 'one'), (2, 'two'), (3, 'three')")

            yield conn

    finally:
        # Drop the testing table and close the connection pool after testcase
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DROP TABLE `test`")

        pool.close()
        await pool.wait_closed()


@pytest.mark.integrationtest
async def test_aiomysql_select(instrument, aiomysql_connection, elasticapm_client):
    try:
        elasticapm_client.begin_transaction("web.django")

        async with aiomysql_connection.cursor() as cursor:
            query = "SELECT * FROM test WHERE `name` LIKE 't%' ORDER BY id"
            await cursor.execute(query)
            assert await cursor.fetchall() == ((2, "two"), (3, "three"))

        elasticapm_client.end_transaction(None, "test-transaction")
    finally:
        transactions = elasticapm_client.events[TRANSACTION]
        spans = elasticapm_client.spans_for_transaction(transactions[0])
        span = spans[0]
        assert span["name"] == "SELECT FROM test"
        assert span["type"] == "db"
        assert span["subtype"] == "mysql"
        assert span["action"] == "query"
        assert "db" in span["context"]
        assert span["context"]["db"]["type"] == "sql"
        assert span["context"]["db"]["statement"] == query
        assert span["context"]["destination"] == {
            "address": os.environ.get("MYSQL_HOST", "localhost"),
            "port": default_ports.get("mysql"),
            "service": {"name": "", "resource": "mysql", "type": ""},
        }
