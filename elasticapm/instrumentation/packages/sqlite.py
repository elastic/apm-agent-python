from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)
from elasticapm.traces import capture_span


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
        kind = "db.sqlite.sql"
        with capture_span(signature, kind, {"db": {"type": "sql", "statement": sql}}):
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

        with capture_span(signature, "db.sqlite.connect"):
            return SQLiteConnectionProxy(wrapped(*args, **kwargs))
