from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.instrumentation.packages.psycopg2 import extract_signature
from opbeat.utils import wrapt

class ConnectionProxy(wrapt.ObjectProxy):
    def __init__(self, wrapped, client):
        super(ConnectionProxy, self).__init__(wrapped)
        self._self_client = client

    def cursor(self, *args, **kwargs):
        return CursorProxy(self.__wrapped__.cursor(*args, **kwargs),
                           self._self_client)


class CursorProxy(wrapt.ObjectProxy):

    def __init__(self, wrapped, client):
        super(CursorProxy, self).__init__(wrapped)
        self._self_client = client

    def callproc(self, procname, params=()):
        return self._trace_sql(self.__wrapped__.callproc, procname,
                               params)

    def execute(self, sql, params=()):
        return self._trace_sql(self.__wrapped__.execute, sql, params)

    def executemany(self, sql, param_list):
        return self._trace_sql(self.__wrapped__.executemany, sql,
                               param_list)

    def _trace_sql(self, method, sql, params):
        signature = extract_signature(sql)
        with self._self_client.capture_trace(signature, "db.sql.sqlite",
                                             {"sql": sql}):
            return method(sql, params)


class SQLLiteInstrumentation(AbstractInstrumentedModule):
    name = 'sqlite'

    instrument_list = [
        ("sqlite3.dbapi2", "connect"),
        ("pysqlite2.dbapi2", "connect"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        return ConnectionProxy(wrapped(*args, **kwargs), self.client)
