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
"""
Instrumentation for Tornado
"""
from elasticapm.instrumentation.packages.asyncio.base import AbstractInstrumentedModule, AsyncAbstractInstrumentedModule


class TornadoRequestExecuteInstrumentation(AsyncAbstractInstrumentedModule):
    name = "tornado_request_execute"

    instrument_list = [("tornado.web.RequestHandler", "_execute")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        # TODO
        ret = await wrapped(*args, **kwargs)

        return ret


class TornadoHandleExceptionInstrumentation(AbstractInstrumentedModule):
    name = "tornado_handle_exception"

    instrument_list = [("tornado.web.RequestHandler", "_handle_exception")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        # TODO
        return wrapped(*args, **kwargs)


class TornadoRenderInstrumentation(AbstractInstrumentedModule):
    name = "tornado_render"

    instrument_list = [("tornado.web.RequestHandler", "render")]

    async def call(self, module, method, wrapped, instance, args, kwargs):
        # TODO
        return wrapped(*args, **kwargs)
