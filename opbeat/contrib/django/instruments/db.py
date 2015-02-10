from django.db import connections
from threading import local


class ThreadLocalState(local):
    def __init__(self):
        self.enabled = True

    @property
    def Wrapper(self):
        return NormalCursorWrapper


state = ThreadLocalState()
# recording = state.recording  # export function


def wrap_cursor(connection):
    if not hasattr(connection, '_djdt_cursor'):
        connection._djdt_cursor = connection.cursor

        def cursor():
            return state.Wrapper(connection._djdt_cursor(), connection)

        connection.cursor = cursor
        return cursor


def enable_instrumentation():
    # This is thread-safe because database connections are thread-local.
    for connection in connections.all():
        wrap_cursor(connection)


class NormalCursorWrapper(object):
    """
    Wraps a cursor and logs queries.
    """

    def __init__(self, cursor, db):
        self.cursor = cursor
        # Instance of a BaseDatabaseWrapper subclass
        self.db = db

    def _quote_params(self, params):
        if not params:
            return params
        if isinstance(params, dict):
            return dict((key, self._quote_expr(value))
                        for key, value in params.items())
        return list(map(self._quote_expr, params))

    def _record(self, name, method, sql, params):
        from opbeat.contrib.django.models import get_client

        alias = getattr(self.db, 'alias', 'default')
        # TODO: normalize/generalize the SQL here.
        with get_client().captureTrace(sql[:200], "sql", {"alias": alias}):
            return method(sql, params)

    def callproc(self, procname, params=()):
        return self._record("callproc", self.cursor.callproc, procname, params)

    def execute(self, sql, params=()):
        return self._record("execute", self.cursor.execute, sql, params)

    def executemany(self, sql, param_list):
        return self._record("executemany", self.cursor.executemany, sql, param_list)

    def __getattr__(self, attr):
        return getattr(self.cursor, attr)

    def __iter__(self):
        return iter(self.cursor)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()