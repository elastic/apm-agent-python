"""Provides classes to instrument dbapi2 providers

https://www.python.org/dev/peps/pep-0249/
"""

from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.utils import wrapt


class CursorProxy(wrapt.ObjectProxy):
    provider_name = None

    def __init__(self, wrapped, client):
        """

        :param wrapped:
        :type wrapped:
        :param client:
        :type client:
        :param provider_name: "postgresql", "sqlite" etc.
        :type provider_name: str
        :param signature_extraction: callable that returns a trace signature
        and takes SQL
        :type signature_extraction: str
        :return:
        :rtype:
        """
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
        signature = self.extract_signature(sql)
        with self._self_client.capture_trace(signature,
                                             "db.sql." + self.provider_name,
                                             {"sql": sql}):
            return method(sql, params)


    def extract_signature(self, sql):
        raise NotImplementedError()

class ConnectionProxy(wrapt.ObjectProxy):
    cursor_proxy = CursorProxy

    def __init__(self, wrapped, client):
        super(ConnectionProxy, self).__init__(wrapped)
        self._self_client = client

    def cursor(self, *args, **kwargs):
        return self.cursor_proxy(self.__wrapped__.cursor(*args, **kwargs),
                                 self._self_client)


class DbApi2Instrumentation(AbstractInstrumentedModule):
    connect_method = None

    def call(self, wrapped, instance, args, kwargs):
        return ConnectionProxy(wrapped(*args, **kwargs), self.client)
