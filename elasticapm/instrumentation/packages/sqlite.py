from elasticapm.instrumentation.packages.dbapi2 import (ConnectionProxy,
                                                        CursorProxy,
                                                        DbApi2Instrumentation,
                                                        extract_signature)
from elasticapm.traces import trace


class SQLiteCursorProxy(CursorProxy):
    provider_name = 'sqlite'

    def extract_signature(self, sql):
        return extract_signature(sql)


class SQLiteConnectionProxy(ConnectionProxy):
    cursor_proxy = SQLiteCursorProxy


class SQLiteInstrumentation(DbApi2Instrumentation):
    name = 'sqlite'

    instrument_list = [
        ("sqlite3", "connect"),
        ("sqlite3.dbapi2", "connect"),
        ("pysqlite2.dbapi2", "connect"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = ".".join([module, method])

        if len(args) == 1:
            signature += " " + str(args[0])

        with trace(signature, "db.sqlite.connect"):
            return SQLiteConnectionProxy(wrapped(*args, **kwargs))
