from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)


class MySQLConnectorCursorProxy(CursorProxy):
    provider_name = "mysql.connector"

    def extract_signature(self, sql):
        return extract_signature(sql)


class MySQLConnectorConnectionProxy(ConnectionProxy):
    cursor_proxy = MySQLConnectorCursorProxy


class MySQLConnectorInstrumentation(DbApi2Instrumentation):
    name = "mysql.connector"

    instrument_list = [("mysql.connector", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        return MySQLConnectorConnectionProxy(wrapped(*args, **kwargs))
