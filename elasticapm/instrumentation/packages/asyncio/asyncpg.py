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
from elasticapm.utils import default_ports


class AsyncPGInstrumentation(AsyncAbstractInstrumentedModule):
    """
    Implement asyncpg instrumentation with two methods Connection.execute
    and Connection.executemany since Connection._do_execute is not called
    given a prepared query is passed to a connection. As in:
    https://github.com/MagicStack/asyncpg/blob/master/asyncpg/connection.py#L294-L297
    """

    name = "asyncpg"

    instrument_list = [
        ("asyncpg.connection", "Connection.execute"),
        ("asyncpg.connection", "Connection.executemany"),
        ("asyncpg.connection", "Connection.fetch"),
        ("asyncpg.connection", "Connection.fetchval"),
        ("asyncpg.connection", "Connection.fetchrow"),
    ]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        query = args[0] if len(args) else kwargs["query"]
        name = extract_signature(query)
        context = {"db": {"type": "sql", "statement": query}}
        action = "query"
        destination_info = {
            "address": kwargs.get("host", "localhost"),
            "port": int(kwargs.get("port", default_ports.get("postgresql"))),
            "service": {"name": "postgres", "resource": "postgres", "type": "db"},
        }
        context["destination"] = destination_info
        async with async_capture_span(
            name, leaf=True, span_type="db", span_subtype="postgres", span_action=action, extra=context
        ):
            return await wrapped(*args, **kwargs)
