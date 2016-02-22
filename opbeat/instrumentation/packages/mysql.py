from opbeat.instrumentation.packages.dbapi2 import (ConnectionProxy,
                                                    CursorProxy,
                                                    DbApi2Instrumentation,
                                                    extract_signature)


class MySQLCursorProxy(CursorProxy):
    provider_name = 'mysql'

    def extract_signature(self, sql):
        return extract_signature(sql)

    def callproc(self, procname, params=None):
        return self._trace_sql(self.__wrapped__.callproc, procname,
                               params)

    def execute(self, sql, params=None):
        return self._trace_sql(self.__wrapped__.execute, sql, params)


class MySQLConnectionProxy(ConnectionProxy):
    cursor_proxy = MySQLCursorProxy


class MySQLInstrumentation(DbApi2Instrumentation):
    name = 'mysql'

    instrument_list = [
        ("MySQLdb", "connect"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        return MySQLConnectionProxy(wrapped(*args, **kwargs))
