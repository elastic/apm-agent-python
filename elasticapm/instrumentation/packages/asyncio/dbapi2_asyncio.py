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

"""Provides classes to instrument dbapi2 providers

https://www.python.org/dev/peps/pep-0249/
"""

import wrapt

from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.instrumentation.packages.dbapi2 import EXEC_ACTION, QUERY_ACTION
from elasticapm.utils.encoding import shorten


class AsyncCursorProxy(wrapt.ObjectProxy):
    provider_name = None
    DML_QUERIES = ("INSERT", "DELETE", "UPDATE")

    def __init__(self, wrapped, destination_info=None):
        super(AsyncCursorProxy, self).__init__(wrapped)
        self._self_destination_info = destination_info or {}

    async def callproc(self, procname, params=None):
        return await self._trace_sql(self.__wrapped__.callproc, procname, params, action=EXEC_ACTION)

    async def execute(self, sql, params=None):
        return await self._trace_sql(self.__wrapped__.execute, sql, params)

    async def executemany(self, sql, param_list):
        return await self._trace_sql(self.__wrapped__.executemany, sql, param_list)

    def _bake_sql(self, sql):
        """
        Method to turn the "sql" argument into a string. Most database backends simply return
        the given object, as it is already a string
        """
        return sql

    async def _trace_sql(self, method, sql, params, action=QUERY_ACTION):
        sql_string = self._bake_sql(sql)
        if action == EXEC_ACTION:
            signature = sql_string + "()"
        else:
            signature = self.extract_signature(sql_string)

        # Truncate sql_string to 10000 characters to prevent large queries from
        # causing an error to APM server.
        sql_string = shorten(sql_string, string_length=10000)

        async with async_capture_span(
            signature,
            span_type="db",
            span_subtype=self.provider_name,
            span_action=action,
            extra={
                "db": {"type": "sql", "statement": sql_string, "instance": getattr(self, "_self_database", None)},
                "destination": self._self_destination_info,
            },
            skip_frames=1,
            leaf=True,
        ) as span:
            if params is None:
                result = await method(sql)
            else:
                result = await method(sql, params)
            # store "rows affected", but only for DML queries like insert/update/delete
            if span and self.rowcount not in (-1, None) and signature.startswith(self.DML_QUERIES):
                span.update_context("db", {"rows_affected": self.rowcount})
            return result

    def extract_signature(self, sql):
        raise NotImplementedError()


class AsyncConnectionProxy(wrapt.ObjectProxy):
    cursor_proxy = AsyncCursorProxy

    def __init__(self, wrapped, destination_info=None):
        super(AsyncConnectionProxy, self).__init__(wrapped)
        self._self_destination_info = destination_info

    def cursor(self, *args, **kwargs):
        return self.cursor_proxy(self.__wrapped__.cursor(*args, **kwargs), self._self_destination_info)


class AsyncDbApi2Instrumentation(AsyncAbstractInstrumentedModule):
    connect_method = None

    async def call(self, module, method, wrapped, instance, args, kwargs):
        return AsyncConnectionProxy(await wrapped(*args, **kwargs))

    async def call_if_sampling(self, module, method, wrapped, instance, args, kwargs):
        # Contrasting to the superclass implementation, we *always* want to
        # return a proxied connection, even if there is no ongoing elasticapm
        # transaction yet. This ensures that we instrument the cursor once
        # the transaction started.
        return await self.call(module, method, wrapped, instance, args, kwargs)
