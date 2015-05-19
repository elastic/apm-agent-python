import re
from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.utils import wrapt


def lookfor_from(tokens):
    literal_opened = None
    seen_from = False

    for idx, token in enumerate(tokens):
        if literal_opened == "'" and token == "'":
            literal_opened = None
            continue
        if literal_opened == "$" and token == "$" and tokens[idx+1] == "$":
            literal_opened = None
            continue

        if literal_opened is None:
            if token == "'":
                literal_opened = "'" if literal_opened is None else None
                continue

            if token == "$" and tokens[idx+1] == "$":
                literal_opened = "$" if literal_opened is None else None
                continue

            if token.upper() == 'FROM':
                seen_from = True
                continue

            if seen_from:
                if token == '(':
                    return lookfor_from(tokens[idx+1:])
                elif token == '"':
                        end_idx = tokens.index('"', idx+1)
                        return "".join(tokens[idx+1:end_idx])
                elif re.match("\w", token):
                    return token


def extract_signature(sql):
    sql = sql.strip()
    first_space = sql.find(' ')
    if first_space < 0:
        return sql

    second_space = sql.find(' ', first_space+1)

    sql_type = sql[0:first_space].upper()

    if sql_type in ['INSERT', 'DELETE']:
        # 2nd word is part of SQL type
        sql_type = sql_type + sql[first_space:second_space]
        # Name is 3rd word
        table_name = sql[second_space+1:sql.index(' ', second_space+1)]
    elif sql_type in ['CREATE', 'DROP']:
        # 2nd word is part of SQL type
        sql_type = sql_type + sql[first_space:second_space]
        table_name = ''
    elif sql_type in ['UPDATE']:
        # Name is 2nd work
        table_name = sql[first_space+1:second_space]
    elif sql_type in ['SELECT']:
        # Name is first table
        try:
            tokens = re.split("(\W)", sql)
            filtered_tokens = [token for token in tokens if token != '']
            sql_type = 'SELECT FROM'
            table_name = lookfor_from(filtered_tokens)
        except IndexError:
            table_name = ''

    else:
        # No name
        table_name = ''

    signature = ' '.join(filter(bool, [sql_type, table_name]))
    return signature

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

