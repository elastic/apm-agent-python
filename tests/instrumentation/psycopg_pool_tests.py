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

from elasticapm.conf.constants import SPAN

psycopg = pytest.importorskip("psycopg")
pool_mod = pytest.importorskip("psycopg_pool")

pytestmark = [pytest.mark.psycopg_pool, pytest.mark.integrationtest]

has_postgres_configured = "POSTGRES_DB" in os.environ


def connect_kwargs():
    return {
        "dbname": os.environ.get("POSTGRES_DB", "elasticapm_test"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "host": os.environ.get("POSTGRES_HOST", None),
        "port": os.environ.get("POSTGRES_PORT", None),
    }


def make_conninfo():
    kw = connect_kwargs()
    host = kw["host"] or "localhost"
    port = kw["port"] or "5432"
    return f"postgresql://{kw['user']}:{kw['password']}@{host}:{port}/{kw['dbname']}"


@pytest.mark.skipif(not has_postgres_configured, reason="PostgreSQL not configured")
def test_pool_generates_spans(instrument, elasticapm_client):
    with pool_mod.ConnectionPool(
        make_conninfo(),
        min_size=1,
        max_size=2,
    ) as pool:
        pool.wait()

        elasticapm_client.begin_transaction("request")
        try:
            with pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
        finally:
            elasticapm_client.end_transaction("200")

    spans = elasticapm_client.events[SPAN]
    # Verify that connect span and query span are generated
    assert len(spans) >= 2
    assert any(span.get("action") == "connect" for span in spans)
    assert any(span.get("context", {}).get("db", {}).get("type") == "sql" for span in spans)
