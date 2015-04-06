from django.db import connections
from threading import local
from opbeat.utils import wrapt
import sqlparse
from sqlparse import tokens, sql
#
# class ThreadLocalState(local):
#     def __init__(self):
#         self.enabled = True
#
#     @property
#     def Wrapper(self):
#         return CursorWrapper


# state = ThreadLocalState()
# recording = state.recording  # export function


def wrap_cursor(connection):
    if not hasattr(connection, '_djdt_cursor'):
        connection._djdt_cursor = connection.cursor

        def cursor():
            return CursorWrapper(connection._djdt_cursor())

        connection.cursor = cursor
        return cursor


def enable_instrumentation():
    # This is thread-safe because database connections are thread-local.
    for connection in connections.all():
        wrap_cursor(connection)


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


class CursorWrapper(wrapt.ObjectProxy):
    """
    Wraps a cursor and logs queries.
    """
    def _record(self, name, method, sql, params):
        from opbeat.contrib.django.models import get_client

        alias = getattr(self.db, 'alias', 'default')

        parsed = sqlparse.parse(sql)[0]
        if parsed.get_type() == 'SELECT':
            signature = "SELECT " + ", ".join(extract_table_identifiers(extract_from_part(parsed)))
        elif parsed.get_type() != 'UNKNOWN':
            signature = parsed.get_type() + " " + parsed.get_name()
        else:
            signature = parsed.get_name()

        with get_client().captureTrace(signature, "sql", {"alias": alias,
                                                          "sql": sql}):
            return method(sql, params)

    def callproc(self, procname, params=()):
        return self._record("callproc", self.__wrapped__.callproc, procname, params)

    def execute(self, sql, params=()):
        return self._record("execute", self.__wrapped__.execute, sql, params)

    def executemany(self, sql, param_list):
        return self._record("executemany", self.__wrapped__.executemany, sql, param_list)
