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


class PyMSSQLCursorProxy(CursorProxy):
    provider_name = "pymssql"

    def extract_signature(self, sql):
        return extract_signature(sql)


class PyMSSQLConnectionProxy(ConnectionProxy):
    cursor_proxy = PyMSSQLCursorProxy


class PyMSSQLInstrumentation(DbApi2Instrumentation):
    name = "pymssql"

    instrument_list = [("pymssql", "connect")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        host, port = get_host_port(args, kwargs)
        destination_info = {
            "address": host,
            "port": port,
            "service": {"name": "mssql", "resource": "mssql", "type": "db"},
        }
        return PyMSSQLConnectionProxy(wrapped(*args, **kwargs), destination_info=destination_info)


def get_host_port(args, kwargs):
    host = args[0] if args else kwargs.get("server")
    port = None
    if not host:
        host = kwargs.get("host", "localhost")
        for sep in (",", ":"):
            if sep in host:
                host, port = host.rsplit(sep, 1)
                port = int(port)
                break
    if not port:
        port = int(kwargs.get("port", default_ports.get("mssql")))
    return host, port
