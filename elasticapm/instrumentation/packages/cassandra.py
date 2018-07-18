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
