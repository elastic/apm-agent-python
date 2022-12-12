#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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


from elasticapm.instrumentation.packages.asyncio.base import AbstractInstrumentedModule
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")


class GRPCClientInstrumentation(AbstractInstrumentedModule):
    name = "grpc_client_instrumentation"
    creates_transactions = True
    instrument_list = [("grpc", "insecure_channel"), ("grpc", "secure_channel")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        import grpc

        from elasticapm.contrib.grpc.client_interceptor import _ClientInterceptor

        result = wrapped(*args, **kwargs)
        target = kwargs.get("target") or args[0]
        if ":" in target:
            host, port = target.split(":")
            try:
                port = int(port)
            except ValueError:
                port = None
        else:
            host, port = None, None
        return grpc.intercept_channel(result, _ClientInterceptor(host, port, secure=method == "secure_channel"))


class GRPCServerInstrumentation(AbstractInstrumentedModule):
    name = "grpc_server_instrumentation"
    creates_transactions = True
    instrument_list = [("grpc", "server")]

    def call(self, module, method, wrapped, instance, args, kwargs):
        from elasticapm.contrib.grpc.server_interceptor import _ServerInterceptor

        interceptors = kwargs.get("interceptors") or (args[2] if len(args) > 2 else [])
        interceptors.insert(0, _ServerInterceptor())
        if len(args) > 2:
            args = list(args)
            args[2] = interceptors
        else:
            kwargs["interceptors"] = interceptors
        return wrapped(*args, **kwargs)
