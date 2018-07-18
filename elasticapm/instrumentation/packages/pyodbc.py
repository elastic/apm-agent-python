from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)


class PyODBCCursorProxy(CursorProxy):
    provider_name = "pyodbc"

    def extract_signature(self, sql):
        return extract_signature(sql)


class PyODBCConnectionProxy(ConnectionProxy):
    cursor_proxy = PyODBCCursorProxy


class PyODBCInstrumentation(DbApi2Instrumentation):
    name = "pyodbc"

    instrument_list = [("pyodbc", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        return PyODBCConnectionProxy(wrapped(*args, **kwargs))
