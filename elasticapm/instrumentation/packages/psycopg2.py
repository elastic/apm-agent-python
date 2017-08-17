from elasticapm.instrumentation.packages.dbapi2 import (ConnectionProxy,
                                                        CursorProxy,
                                                        DbApi2Instrumentation,
                                                        extract_signature)
from elasticapm.traces import trace
from elasticapm.utils import default_ports


class PGCursorProxy(CursorProxy):
    provider_name = 'postgresql'

    def extract_signature(self, sql):
        return extract_signature(sql)


class PGConnectionProxy(ConnectionProxy):
    cursor_proxy = PGCursorProxy


class Psycopg2Instrumentation(DbApi2Instrumentation):
    name = 'psycopg2'

    instrument_list = [
        ("psycopg2", "connect")
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = "psycopg2.connect"

        host = kwargs.get('host')
        if host:
            signature += " " + str(host)

            port = kwargs.get('port')
            if port:
                port = str(port)
                if int(port) != default_ports.get("postgresql"):
                    signature += ":" + port
        else:
            # Parse connection string and extract host/port
            pass

        with trace(signature, "db.postgreql.connect"):
            return PGConnectionProxy(wrapped(*args, **kwargs))


class Psycopg2RegisterTypeInstrumentation(DbApi2Instrumentation):
    name = 'psycopg2-register-type'

    instrument_list = [
        ("psycopg2.extensions", "register_type"),
        # specifically instrument `register_json` as it bypasses `register_type`
        ("psycopg2._json", "register_json"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if ('conn_or_curs' in kwargs and
                hasattr(kwargs['conn_or_curs'], "__wrapped__")):
            kwargs['conn_or_curs'] = kwargs['conn_or_curs'].__wrapped__
        # register_type takes the connection as second argument
        elif len(args) == 2 and hasattr(args[1], "__wrapped__"):
                args = (args[0], args[1].__wrapped__)
        # register_json takes the connection as first argument, and can have
        # several more arguments
        elif method == 'register_json':
            if args and hasattr(args[0], "__wrapped__"):
                args = (args[0].__wrapped__,) + args[1:]

        return wrapped(*args, **kwargs)
