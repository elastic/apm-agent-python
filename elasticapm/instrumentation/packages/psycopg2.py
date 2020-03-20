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

from elasticapm.instrumentation.packages.dbapi2 import (
    ConnectionProxy,
    CursorProxy,
    DbApi2Instrumentation,
    extract_signature,
)
from elasticapm.traces import capture_span
from elasticapm.utils import compat, default_ports


class PGCursorProxy(CursorProxy):
    provider_name = "postgresql"

    def _bake_sql(self, sql):
        # if this is a Composable object, use its `as_string` method
        # see http://initd.org/psycopg/docs/sql.html
        if hasattr(sql, "as_string"):
            return sql.as_string(self.__wrapped__)
        return sql

    def extract_signature(self, sql):
        return extract_signature(sql)

    def __enter__(self):
        return PGCursorProxy(self.__wrapped__.__enter__(), destination_info=self._self_destination_info)


class PGConnectionProxy(ConnectionProxy):
    cursor_proxy = PGCursorProxy

    def __enter__(self):
        return PGConnectionProxy(self.__wrapped__.__enter__(), destination_info=self._self_destination_info)


class Psycopg2Instrumentation(DbApi2Instrumentation):
    name = "psycopg2"

    instrument_list = [("psycopg2", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        signature = "psycopg2.connect"

        host = kwargs.get("host")
        if host:
            signature += " " + compat.text_type(host)

            port = kwargs.get("port")
            if port:
                port = str(port)
                if int(port) != default_ports.get("postgresql"):
                    host += ":" + port
            signature += " " + compat.text_type(host)
        else:
            # Parse connection string and extract host/port
            pass
        destination_info = {
            "address": kwargs.get("host", "localhost"),
            "port": int(kwargs.get("port", default_ports.get("postgresql"))),
            "service": {"name": "postgresql", "resource": "postgresql", "type": "db"},
        }
        with capture_span(
            signature,
            span_type="db",
            span_subtype="postgresql",
            span_action="connect",
            extra={"destination": destination_info},
        ):
            return PGConnectionProxy(wrapped(*args, **kwargs), destination_info=destination_info)


class Psycopg2ExtensionsInstrumentation(DbApi2Instrumentation):
    """
    Some extensions do a type check on the Connection/Cursor in C-code, which our
    proxy fails. For these extensions, we need to ensure that the unwrapped
    Connection/Cursor is passed.
    """

    name = "psycopg2"

    instrument_list = [
        ("psycopg2.extensions", "register_type"),
        # specifically instrument `register_json` as it bypasses `register_type`
        ("psycopg2._json", "register_json"),
        ("psycopg2.extensions", "quote_ident"),
        ("psycopg2.extensions", "encrypt_password"),
    ]

    def call(self, module, method, wrapped, instance, args, kwargs):
        if "conn_or_curs" in kwargs and hasattr(kwargs["conn_or_curs"], "__wrapped__"):
            kwargs["conn_or_curs"] = kwargs["conn_or_curs"].__wrapped__
        # register_type takes the connection as second argument
        elif len(args) == 2 and hasattr(args[1], "__wrapped__"):
            args = (args[0], args[1].__wrapped__)
        # register_json takes the connection as first argument, and can have
        # several more arguments
        elif method == "register_json":
            if args and hasattr(args[0], "__wrapped__"):
                args = (args[0].__wrapped__,) + args[1:]

        elif method == "encrypt_password":
            # connection/cursor is either 3rd argument, or "scope" keyword argument
            if len(args) >= 3 and hasattr(args[2], "__wrapped__"):
                args = args[:2] + (args[2].__wrapped__,) + args[3:]
            elif "scope" in kwargs and hasattr(kwargs["scope"], "__wrapped__"):
                kwargs["scope"] = kwargs["scope"].__wrapped__

        return wrapped(*args, **kwargs)
