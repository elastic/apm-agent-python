"""Provides classes to instrument dbapi2 providers

https://www.python.org/dev/peps/pep-0249/
"""
import re

from opbeat.instrumentation.packages.base import AbstractInstrumentedModule
from opbeat.traces import trace
from opbeat.utils import wrapt


class Literal(object):
    def __init__(self, literal_type, content):
        self.literal_type = literal_type
        self.content = content

    def __eq__(self, other):
        return (isinstance(other, Literal)
                and self.literal_type == other.literal_type
                and self.content == other.content)

    def __repr__(self):
        return "<Literal {}{}{}>".format(self.literal_type, self.content,
                                         self.literal_type)


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


def look_for_table(sql, keyword):
    tokens = tokenize(sql)
    table_name = _scan_for_table_with_tokens(tokens, keyword)
    if isinstance(table_name, Literal):
        table_name = table_name.content.strip(table_name.literal_type)
    return table_name


def _scan_for_table_with_tokens(tokens, keyword):
    seen_keyword = False
    for idx, lexeme in scan(tokens):
        if seen_keyword:
            if lexeme == "(":
                return _scan_for_table_with_tokens(tokens[idx:], keyword)
            else:
                return lexeme

        if lexeme == keyword:
            seen_keyword = True


def tokenize(sql):
    return [t for t in re.split("(\W)", sql) if t != '']


def scan(tokens):
    literal_start_idx = None
    literal_started = None
    prev_was_escape = False
    lexeme = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if literal_start_idx:
            if prev_was_escape:
                prev_was_escape = False
                lexeme.append(token)
            else:

                if token == literal_started:
                    if (literal_started == "'" and len(tokens) >= i+1
                            and tokens[i+1] == "'"):  # double quotes
                        i += 1
                        lexeme.append("'")
                    else:
                        yield i, Literal(literal_started, "".join(lexeme))
                        literal_start_idx = None
                        literal_started = None
                        lexeme = []
                else:
                    if token == '\\':
                        prev_was_escape = token
                    else:
                        prev_was_escape = False
                        lexeme.append(token)
        elif literal_start_idx is None:
            if token in ["'", '"', "`"]:
                literal_start_idx = i
                literal_started = token
            elif token == "$":
                # Postgres can use arbitrary characters between two $'s as a
                # literal separation token, e.g.: $fish$ literal $fish$
                # This part will detect that and skip over the literal.
                skipped_token = skip_to(i+1, tokens, '$')
                if skipped_token is not None:
                    dollar_token = ['$'] + skipped_token

                    skipped = skip_to(i + len(dollar_token), tokens,
                                      dollar_token)
                    if skipped:  # end wasn't found.
                        yield i, Literal("".join(dollar_token),
                                         "".join(skipped[:-len(dollar_token)]))
                        i = i + len(skipped) + len(dollar_token)
            else:
                if token != ' ':
                    yield i, token
        i += 1

    if lexeme:
        yield i, lexeme


def extract_signature(sql):
    sql = sql.strip()
    first_space = sql.find(' ')
    if first_space < 0:
        return sql

    second_space = sql.find(' ', first_space+1)

    sql_type = sql[0:first_space].upper()

    if sql_type in ['INSERT', 'DELETE']:
        keyword = 'INTO' if sql_type == 'INSERT' else 'FROM'
        sql_type = sql_type + " " + keyword

        table_name = look_for_table(sql, keyword)
    elif sql_type in ['CREATE', 'DROP']:
        # 2nd word is part of SQL type
        sql_type = sql_type + sql[first_space:second_space]
        table_name = ''
    elif sql_type == 'UPDATE':
        table_name = look_for_table(sql, "UPDATE")
    elif sql_type == 'SELECT':
        # Name is first table
        try:
            sql_type = 'SELECT FROM'
            table_name = look_for_table(sql, "FROM")
        except:
            table_name = ''
    else:
        # No name
        table_name = ''

    signature = ' '.join(filter(bool, [sql_type, table_name]))
    return signature


class CursorProxy(wrapt.ObjectProxy):
    provider_name = None

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
        kind = "db.{0}.sql".format(self.provider_name)
        with trace(signature, kind, {"sql": sql}):
            return method(sql, params)

    def extract_signature(self, sql):
        raise NotImplementedError()


class ConnectionProxy(wrapt.ObjectProxy):
    cursor_proxy = CursorProxy

    def cursor(self, *args, **kwargs):
        return self.cursor_proxy(self.__wrapped__.cursor(*args, **kwargs))


class DbApi2Instrumentation(AbstractInstrumentedModule):
    connect_method = None

    def call(self, module, method, wrapped, instance, args, kwargs):
        return ConnectionProxy(wrapped(*args, **kwargs))
