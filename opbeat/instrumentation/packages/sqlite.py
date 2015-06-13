from opbeat.instrumentation.packages.dbapi2 import (CursorProxy,
                                                    ConnectionProxy,
                                                    DbApi2Instrumentation)
from opbeat.instrumentation.packages.psycopg2 import extract_signature


class SQLiteCursorProxy(CursorProxy):
    provider_name = 'sqlite'

    def extract_signature(self, sql):
        return extract_signature(sql)

class SQLiteConnectionProxy(ConnectionProxy):
    cursor_proxy = SQLiteCursorProxy

class SQLiteInstrumentation(DbApi2Instrumentation):
    name = 'sqlite'

    instrument_list = [
        ("sqlite3.dbapi2", "connect"),
        ("pysqlite2.dbapi2", "connect"),
    ]

    def call(self, wrapped, instance, args, kwargs):
        return SQLiteConnectionProxy(wrapped(*args, **kwargs), self.client)
