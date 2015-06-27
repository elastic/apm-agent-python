from opbeat.instrumentation.packages.dbapi2 import (ConnectionProxy,
                                                    CursorProxy,
                                                    DbApi2Instrumentation,
                                                    extract_signature)
from opbeat.utils import default_ports



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

        with self.client.capture_trace(signature, "db.postgreql.connect"):
            return PGConnectionProxy(wrapped(*args, **kwargs), self.client)
