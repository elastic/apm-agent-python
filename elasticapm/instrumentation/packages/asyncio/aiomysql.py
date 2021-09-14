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

from elasticapm.contrib.asyncio.traces import async_capture_span
from elasticapm.instrumentation.packages.asyncio.base import AsyncAbstractInstrumentedModule
from elasticapm.instrumentation.packages.dbapi2 import extract_signature
from elasticapm.utils.encoding import shorten


class AioMySQLInstrumentation(AsyncAbstractInstrumentedModule):
    name = "aiomysql"

    instrument_list = [("aiomysql.cursors", "Cursor.execute")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        if method == "Cursor.execute":
            query = args[0]
            name = extract_signature(query)

            # Truncate sql_string to 10000 characters to prevent large queries from
            # causing an error to APM server.
            query = shorten(query, string_length=10000)

            context = {
                "db": {"type": "sql", "statement": query},
                "destination": {
                    "address": instance.connection.host,
                    "port": instance.connection.port,
                    "service": {"name": "mysql", "resource": "mysql", "type": "db"},
                },
            }
            action = "query"
        else:
            raise AssertionError("call from uninstrumented method")

        async with async_capture_span(
            name, leaf=True, span_type="db", span_subtype="mysql", span_action=action, extra=context
        ):
            return await wrapped(*args, **kwargs)
