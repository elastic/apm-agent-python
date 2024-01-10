#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Provides classes to instrument dbapi2 providers

https://www.python.org/dev/peps/pep-0249/
"""

import re

import wrapt

from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.traces import capture_span
from elasticapm.utils.encoding import force_text, shorten


class Literal(object):
    def __init__(self, literal_type, content) -> None:
        self.literal_type = literal_type
        self.content = content

    def __eq__(self, other):
        return isinstance(other, Literal) and self.literal_type == other.literal_type and self.content == other.content

    def __repr__(self):
        return "<Literal {}{}{}>".format(self.literal_type, self.content, self.literal_type)


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

        if isinstance(lexeme, str) and lexeme.upper() == keyword:
            seen_keyword = True


def tokenize(sql):
    # split on anything that is not a word character or a square bracket, excluding dots
    return [t for t in re.split(r"([^\w.\[\]])", sql) if t != ""]


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
                    if literal_started == "'" and len(tokens) > i + 1 and tokens[i + 1] == "'":  # double quotes
                        i += 1
                        lexeme.append("'")
                    else:
                        yield i, Literal(literal_started, "".join(lexeme))
                        literal_start_idx = None
                        literal_started = None
                        lexeme = []
                else:
                    if token == "\\":
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
                try:
                    # Closing dollar of the opening quote,
                    # i.e. the second $ in the first $fish$
                    closing_dollar_idx = tokens.index("$", i + 1)
                except ValueError:
                    pass
                else:
                    quote = tokens[i : closing_dollar_idx + 1]
                    length = len(quote)
                    # Opening dollar of the closing quote,
                    # i.e. the first $ in the second $fish$
                    closing_quote_idx = closing_dollar_idx + 1
                    while True:
                        try:
                            closing_quote_idx = tokens.index("$", closing_quote_idx)
                        except ValueError:
                            break
                        if tokens[closing_quote_idx : closing_quote_idx + length] == quote:
                            yield i, Literal(
                                "".join(quote), "".join(tokens[closing_dollar_idx + 1 : closing_quote_idx])
                            )
                            i = closing_quote_idx + length
                            break
                        closing_quote_idx += 1
            else:
                if token != " ":
                    yield i, token
        i += 1

    if lexeme:
        yield i, lexeme


def extract_signature(sql):
    """
    Extracts a minimal signature from a given SQL query
    :param sql: the SQL statement
    :return: a string representing the signature
    """
    sql = force_text(sql)
    sql = sql.strip()
    first_space = sql.find(" ")
    if first_space < 0:
        return sql

    second_space = sql.find(" ", first_space + 1)

    sql_type = sql[0:first_space].upper()

    if sql_type in ["INSERT", "DELETE"]:
        keyword = "INTO" if sql_type == "INSERT" else "FROM"
        sql_type = sql_type + " " + keyword

        object_name = look_for_table(sql, keyword)
    elif sql_type in ["CREATE", "DROP"]:
        # 2nd word is part of SQL type
        sql_type = sql_type + sql[first_space:second_space]
        object_name = ""
    elif sql_type == "UPDATE":
        object_name = look_for_table(sql, "UPDATE")
    elif sql_type == "SELECT":
        # Name is first table
        try:
            sql_type = "SELECT FROM"
            object_name = look_for_table(sql, "FROM")
        except Exception:
            object_name = ""
    elif sql_type in ["EXEC", "EXECUTE"]:
        sql_type = "EXECUTE"
        end = second_space if second_space > first_space else len(sql)
        object_name = sql[first_space + 1 : end]
    elif sql_type == "CALL":
        first_paren = sql.find("(", first_space)
        end = first_paren if first_paren > first_space else len(sql)
        procedure_name = sql[first_space + 1 : end].rstrip(";")
        object_name = procedure_name + "()"
    else:
        # No name
        object_name = ""

    signature = " ".join(filter(bool, [sql_type, object_name]))
    return signature


QUERY_ACTION = "query"
EXEC_ACTION = "exec"
PROCEDURE_STATEMENTS = ["EXEC", "EXECUTE", "CALL"]


def extract_action_from_signature(signature, default):
    if signature.split(" ")[0] in PROCEDURE_STATEMENTS:
        return EXEC_ACTION
    return default


class CursorProxy(wrapt.ObjectProxy):
    provider_name = None
    DML_QUERIES = ("INSERT", "DELETE", "UPDATE")

    def __init__(self, wrapped, destination_info=None) -> None:
        super(CursorProxy, self).__init__(wrapped)
        self._self_destination_info = destination_info or {}

    def callproc(self, procname, params=None):
        return self._trace_sql(self.__wrapped__.callproc, procname, params, action=EXEC_ACTION)

    def execute(self, sql, params=None):
        return self._trace_sql(self.__wrapped__.execute, sql, params)

    def executemany(self, sql, param_list):
        return self._trace_sql(self.__wrapped__.executemany, sql, param_list)

    def _bake_sql(self, sql):
        """
        Method to turn the "sql" argument into a string. Most database backends simply return
        the given object, as it is already a string
        """
        return sql

    def _trace_sql(self, method, sql, params, action=QUERY_ACTION):
        sql_string = self._bake_sql(sql)
        if action == EXEC_ACTION:
            signature = sql_string + "()"
        else:
            signature = self.extract_signature(sql_string)
            action = extract_action_from_signature(signature, action)

        # Truncate sql_string to 10000 characters to prevent large queries from
        # causing an error to APM server.
        sql_string = shorten(sql_string, string_length=10000)

        with capture_span(
            signature,
            span_type="db",
            span_subtype=self.provider_name,
            span_action=action,
            extra={
                "db": {"type": "sql", "statement": sql_string, "instance": getattr(self, "_self_database", None)},
                "destination": self._self_destination_info,
            },
            skip_frames=1,
            leaf=True,
        ) as span:
            if params is None:
                result = method(sql)
            else:
                result = method(sql, params)
            # store "rows affected", but only for DML queries like insert/update/delete
            if span and self.rowcount not in (-1, None) and signature.startswith(self.DML_QUERIES):
                span.update_context("db", {"rows_affected": self.rowcount})
            return result

    def extract_signature(self, sql):
        raise NotImplementedError()


class ConnectionProxy(wrapt.ObjectProxy):
    cursor_proxy = CursorProxy

    def __init__(self, wrapped, destination_info=None) -> None:
        super(ConnectionProxy, self).__init__(wrapped)
        self._self_destination_info = destination_info

    def cursor(self, *args, **kwargs):
        return self.cursor_proxy(self.__wrapped__.cursor(*args, **kwargs), self._self_destination_info)


class DbApi2Instrumentation(AbstractInstrumentedModule):
    connect_method = None

    def call(self, module, method, wrapped, instance, args, kwargs):
        return ConnectionProxy(wrapped(*args, **kwargs))

    def call_if_sampling(self, module, method, wrapped, instance, args, kwargs):
        # Contrasting to the superclass implementation, we *always* want to
        # return a proxied connection, even if there is no ongoing elasticapm
        # transaction yet. This ensures that we instrument the cursor once
        # the transaction started.
        return self.call(module, method, wrapped, instance, args, kwargs)
