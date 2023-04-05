#  BSD 3-Clause License
#
#  Copyright (c) 2023, Elasticsearch BV
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

import os

from elasticapm import Client, get_client
from elasticapm.contrib.serverless.aws import _lambda_transaction, prep_kwargs
from elasticapm.instrumentation.packages.base import AbstractInstrumentedModule
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.instrument")


class LambdaInstrumentation(AbstractInstrumentedModule):
    name = "lambda"

    creates_transactions = True

    def get_instrument_list(self):
        handler = os.environ.get("_HANDLER", None)
        if handler:
            handler = handler.rsplit(".", 1)
            return [handler]
        logger.debug(f"Lambda instrumentation failed: no handler found. _HANDLER: {handler}")
        return []

    def call(self, module, method, wrapped, instance, args, kwargs):
        client_kwargs = prep_kwargs()
        client = get_client()
        if not client:
            client = Client(**client_kwargs)
        if len(args) >= 2:
            event, context = args[0:2]
        else:
            event, context = {}, {}
        if not client.config.debug and client.config.instrument and client.config.enabled:
            with _lambda_transaction(wrapped, None, client, event, context) as sls:
                sls.response = wrapped(*args, **kwargs)
                return sls.response
        else:
            return wrapped(*args, **kwargs)
