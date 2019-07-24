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
