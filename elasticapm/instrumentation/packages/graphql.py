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

from elasticapm import set_transaction_name
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span


class GraphQLExecutorInstrumentation(AbstractInstrumentedModule):
    name = "graphql"

    instrument_list = [
        ("graphql.execution.executors.sync", "SyncExecutor.execute"),
        ("graphql.execution.executors.gevent", "GeventExecutor.execute"),
        ("graphql.execution.executors.asyncio", "AsyncioExecutor.execute"),
        ("graphql.execution.executors.process", "ProcessExecutor.execute"),
        ("graphql.execution.executors.thread", "ThreadExecutor.execute_in_thread"),
        ("graphql.execution.executors.thread", "ThreadExecutor.execute_in_pool"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        name = "GraphQL"

        info = ""
        query = args[2]

        if "ResolveInfo" == type(query).__name__:
            if str(query.return_type).rstrip("!") in [
                "Boolean",
                "Context",
                "Date",
                "DateTime",
                "Decimal",
                "Dynamic",
                "Float",
                "ID",
                "Int",
                "String",
                "Time",
                "UUID",
                "Boolean",
                "String",
            ]:
                return wrapped(*args, **kwargs)

            op = query.operation.operation
            field = query.field_name
            info = "%s %s" % (op, field)
        elif "RequestParams" == type(query).__name__:
            info = "%s %s" % ("request", query.query)
        else:
            info = str(query)

        with capture_span("%s.%s" % (name, info), span_type="external", span_subtype="graphql", span_action="query"):
            return wrapped(*args, **kwargs)


class GraphQLBackendInstrumentation(AbstractInstrumentedModule):
    name = "graphql"

    instrument_list = [
        ("graphql.backend.core", "GraphQLCoreBackend.document_from_string"),
        ("graphql.backend.cache", "GraphQLCachedBackend.document_from_string"),
    ]

    def get_graphql_tx_name(self, graphql_doc):
        try:
            op_def = [i for i in graphql_doc.definitions if type(i).__name__ == "OperationDefinition"][0]
        except KeyError:
            return "GraphQL unknown operation"

        op = op_def.operation
        name = op_def.name
        fields = op_def.selection_set.selections
        return "GraphQL %s %s" % (op.upper(), name if name else "+".join([f.name.value for f in fields]))

    def call(self, module, method, wrapped, instance, args, kwargs):
        graphql_document = wrapped(*args, **kwargs)
        transaction_name = self.get_graphql_tx_name(graphql_document.document_ast)
        set_transaction_name(transaction_name)
        return graphql_document
