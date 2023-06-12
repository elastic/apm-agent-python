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
from __future__ import absolute_import

from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)
from elasticapm.instrumentation.packages.psycopg2 import get_destination_info
from elasticapm.traces import capture_span


class PGCursorProxy(CursorProxy):
    provider_name = "postgresql"

    def _bake_sql(self, sql):
        # If this is a Composable object, use its `as_string` method.
        # See https://www.psycopg.org/psycopg3/docs/api/sql.html
        if hasattr(sql, "as_string"):
            sql = sql.as_string(self.__wrapped__)
        # If the sql string is already a byte string, we need to decode it using the connection encoding
        if isinstance(sql, bytes):
            sql = sql.decode(self.connection.info.encoding)
        return sql

    def extract_signature(self, sql):
        return extract_signature(sql)

    def __enter__(self):
        return PGCursorProxy(self.__wrapped__.__enter__(), destination_info=self._self_destination_info)

    @property
    def _self_database(self):
        return self.connection.info.dbname or ""


class PGConnectionProxy(ConnectionProxy):
    cursor_proxy = PGCursorProxy

    def __enter__(self):
        return PGConnectionProxy(self.__wrapped__.__enter__(), destination_info=self._self_destination_info)


class PsycopgInstrumentation(DbApi2Instrumentation):
    name = "psycopg"

    instrument_list = [("psycopg", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = "psycopg.connect"

        host, port = get_destination_info(kwargs.get("host"), kwargs.get("port"))
        database = kwargs.get("dbname")
        signature = f"{signature} {host}:{port}"
        destination_info = {
            "address": host,
            "port": port,
        }
        with capture_span(
            signature,
            span_type="db",
            span_subtype="postgresql",
            span_action="connect",
            leaf=True,
            extra={"destination": destination_info, "db": {"type": "sql", "instance": database}},
        ):
            return PGConnectionProxy(wrapped(*args, **kwargs), destination_info=destination_info)
