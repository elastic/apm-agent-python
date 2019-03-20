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

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.instrumentation.packages.dbapi2 import extract_signature
from elasticapm.traces import capture_span
from elasticapm.utils import compat


class CassandraInstrumentation(AbstractInstrumentedModule):
    name = "cassandra"

    instrument_list = [("cassandra.cluster", "Session.execute"), ("cassandra.cluster", "Cluster.connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = self.get_wrapped_name(wrapped, instance, method)
        context = None
        if method == "Cluster.connect":
            span_type = "db.cassandra.connect"
        else:
            span_type = "db.cassandra.query"
            query = args[0] if args else kwargs.get("query")
            if hasattr(query, "query_string"):
                query_str = query.query_string
            elif hasattr(query, "prepared_statement") and hasattr(query.prepared_statement, "query"):
                query_str = query.prepared_statement.query
            elif isinstance(query, compat.string_types):
                query_str = query
            else:
                query_str = None
            if query_str:
                name = extract_signature(query_str)
                context = {"db": {"type": "sql", "statement": query_str}}

        with capture_span(name, span_type, context):
            return wrapped(*args, **kwargs)
