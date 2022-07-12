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
from elasticapm.utils import default_ports


class MySQLCursorProxy(CursorProxy):
    provider_name = "mysql"

    def extract_signature(self, sql):
        return extract_signature(sql)


class MySQLConnectionProxy(ConnectionProxy):
    cursor_proxy = MySQLCursorProxy

    def cursor(self, *args, **kwargs):
        c = super().cursor(*args, **kwargs)
        c._self_database = self._self_database
        return c


class MySQLInstrumentation(DbApi2Instrumentation):
    name = "mysql"

    instrument_list = [("MySQLdb", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        destination_info = {
            "address": args[0] if len(args) else kwargs.get("host", "localhost"),
            "port": args[4] if len(args) > 4 else int(kwargs.get("port", default_ports.get("mysql"))),
        }
        proxy = MySQLConnectionProxy(wrapped(*args, **kwargs), destination_info=destination_info)
        proxy._self_database = kwargs.get("database", kwargs.get("db", ""))
        return proxy
