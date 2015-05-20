import re
from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.utils import wrapt


def skip_to(start, tokens, value_sequence):
    i = start
    while i < len(tokens):
        for idx, token in enumerate(value_sequence):
            if tokens[i+idx] != token:
                break
        else:
            # Match
            return tokens[start:i+len(value_sequence)]
        i += 1

    # Not found
    return None

def lookfor_from(tokens):
    literal_opened = None
    seen_from = False
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if literal_opened == "'" and token == "'":
            literal_opened = None
        elif literal_opened is None:
            if token == "'":
                literal_opened = "'"
            elif token == "$":
                # Postgres can use arbitrary characters between two $'s as a
                # literal separation token, e.g.: $fish$ literal $fish$
                # This part will detect that and skip over the literal.
                dollar_token = ['$'] + skip_to(i+1, tokens, ['$'])
                i = i + len(dollar_token) + 1
                skipped = skip_to(i, tokens, dollar_token)
                if not skipped:  # end wasn't found
                    return ""
                i = i + len(skipped) + 1
            elif token.upper() == 'FROM':
                seen_from = True
            elif seen_from:
                if token == '(':
                    return lookfor_from(tokens[i+1:])
                elif token == '"':
                        end_idx = tokens.index('"', i+1)
                        return "".join(tokens[i+1:end_idx])
                elif re.match("\w", token):
                    return token
        i += 1


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

