# -*- coding: utf-8 -*-

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
from elasticapm.instrumentation.packages.mysql import extract_signature

mysqldb = pytest.importorskip("MySQLdb")


pytestmark = [pytest.mark.mysqlclient]

if "MYSQL_HOST" not in os.environ:
    pytestmark.append(pytest.mark.skip("Skipping mysqlclient tests, no MYSQL_HOST environment variable set"))


@pytest.yield_fixture(scope="function")
def mysqlclient_connection(request):
    conn = mysqldb.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "eapm"),
        password=os.environ.get("MYSQL_PASSWORD", "Very(!)Secure"),
        database=os.environ.get("MYSQL_DATABASE", "eapm_tests"),
    )
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE `test` (`id` INT, `name` VARCHAR(5))")
    cursor.execute("INSERT INTO `test` (`id`, `name`) VALUES (1, 'one'), (2, 'two'), (3, 'three')")
    row = cursor.fetchone()
    print(row)

    yield conn

    cursor.execute("DROP TABLE `test`")


@pytest.mark.integrationtest
def test_mysql_connector_select(instrument, mysqlclient_connection, elasticapm_client):
    cursor = mysqlclient_connection.cursor()
    query = "SELECT * FROM test WHERE name LIKE 't%' ORDER BY id"

    try:
        elasticapm_client.begin_transaction("web.django")
        cursor.execute(query)
        assert cursor.fetchall() == ((2, "two"), (3, "three"))
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
            "address": "mysql",
            "port": 3306,
            "service": {"name": "mysql", "resource": "mysql", "type": "db"},
        }
