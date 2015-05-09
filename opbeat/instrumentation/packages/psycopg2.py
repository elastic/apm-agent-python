from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.utils import wrapt
from opbeat.utils import sqlparse
from opbeat.utils.sqlparse import tokens, sql



def is_subselect(parsed):
    if not parsed.is_group():
        return False
    for item in parsed.tokens:
        if item.ttype is tokens.DML and item.value.upper() == 'SELECT':
            return True
    return False


def extract_from_part(parsed):
    from_seen = False
    for item in parsed.tokens:
        if from_seen:
            if is_subselect(item):
                for x in extract_from_part(item):
                    yield x
            elif item.ttype is tokens.Keyword:
                raise StopIteration
            else:
                yield item
        elif item.ttype is tokens.Keyword and item.value.upper() == 'FROM':
            from_seen = True


def extract_table_identifiers(token_stream):
    for item in token_stream:
        if isinstance(item, sql.IdentifierList):
            for identifier in item.get_identifiers():
                yield identifier.get_name()
        elif isinstance(item, sql.Identifier):
            yield item.get_name()
        # It's a bug to check for Keyword here, but in the example
        # above some tables names are identified as keywords...
        elif item.ttype is tokens.Keyword:
            yield item.value


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
        parsed = sqlparse.parse(sql)[0]
        sql_type = parsed.get_type()

        if sql_type == 'SELECT':
            signature = "SELECT " + ", ".join(
                extract_table_identifiers(extract_from_part(parsed)))
        elif sql_type and sql_type != 'UNKNOWN':
            signature = parsed.get_type()

            if parsed.get_name():
                signature += " " + parsed.get_name()
        else:
            if parsed.get_name():
                signature = parsed.get_name()
            else:
                signature = "SQL"

        with self._self_client.capture_trace(signature, "db.sql.postgresql",
                                             {"sql": sql}):
            return method(sql, params)


class Psycopg2Instrumentation(AbstractInstrumentedModule):
    name = 'psycopg2'

    instrument_list = [
        ("psycopg2", "connect")
    ]

    def call(self, wrapped, instance, args, kwargs):
        return ConnectionProxy(wrapped(*args, **kwargs), self.client)


