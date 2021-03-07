#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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

from inspect import isawaitable, iscoroutinefunction

from sanic.handlers import ErrorHandler

from elasticapm.contrib.sanic.sanic_types import ApmHandlerType


class ElasticAPMPatchedErrorHandler(ErrorHandler):
    """
    This is a monkey patchable instance of the Sanic's Error handler infra. Current implementation of Sanic doesn't
    let you chain exception handlers by raising exception chains further down the line. In order to bypass this
    limitation, we monkey patch the current implementation. We invoke the instrumentation function first and then
    chain the exception down to the original handler so that we don't get in the way of standard exception handling.
    """

    def __init__(self):
        super(ElasticAPMPatchedErrorHandler, self).__init__()
        self._apm_handler = None  # type: ApmHandlerType

    def setup_apm_handler(self, apm_handler: ApmHandlerType, force: bool = False):
        if self._apm_handler is None or force:
            self._apm_handler = apm_handler

    async def _patched_response(self, request, exception, default=False):
        await self._apm_handler(request, exception)
        if not default:
            resp = super(ElasticAPMPatchedErrorHandler, self).response(request=request, exception=exception)
        else:
            resp = super(ElasticAPMPatchedErrorHandler, self).default(request=request, exception=exception)
        if iscoroutinefunction(resp) or isawaitable(resp):
            return await resp
        return resp

    def response(self, request, exception):
        return self._patched_response(request=request, exception=exception)

    def default(self, request, exception):
        return self._patched_response(request=request, exception=exception, default=True)
