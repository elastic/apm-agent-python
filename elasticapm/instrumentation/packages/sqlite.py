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

from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)
from elasticapm.traces import capture_span
from elasticapm.utils.encoding import shorten


class SQLiteCursorProxy(CursorProxy):
    provider_name = "sqlite"

    def extract_signature(self, sql):
        return extract_signature(sql)


class SQLiteConnectionProxy(ConnectionProxy):
    cursor_proxy = SQLiteCursorProxy

    # we need to implement wrappers for the non-standard Connection.execute and
    # Connection.executemany methods

    def _trace_sql(self, method, sql, params):
        signature = extract_signature(sql)
        sql_string = shorten(sql, string_length=10000)
        with capture_span(
            signature,
            span_type="db",
            span_subtype="sqlite",
            span_action="query",
            extra={"db": {"type": "sql", "statement": sql_string}},
        ):
            if params is None:
                return method(sql)
            else:
                return method(sql, params)

    def execute(self, sql, params=None):
        return self._trace_sql(self.__wrapped__.execute, sql, params)

    def executemany(self, sql, params=None):
        return self._trace_sql(self.__wrapped__.executemany, sql, params)


class SQLiteInstrumentation(DbApi2Instrumentation):
    name = "sqlite"

    instrument_list = [("sqlite3", "connect"), ("sqlite3.dbapi2", "connect"), ("pysqlite2.dbapi2", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = ".".join([module, method])

        if len(args) == 1:
            signature += " " + str(args[0])

        with capture_span(signature, span_type="db", span_subtype="sqlite", span_action="connect"):
            return SQLiteConnectionProxy(wrapped(*args, **kwargs))
