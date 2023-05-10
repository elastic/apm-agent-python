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
from importlib import import_module

import elasticapm
from elasticapm import Client, get_client
from elasticapm.contrib.serverless.aws import _lambda_transaction, prep_kwargs
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.lambda")

# Prep client and instrument
# For some reason, if we instrument as part of our handler, it adds 3+ seconds
# to the cold start time. So we do it here. I still don't know why this slowdown
# happens.
client_kwargs = prep_kwargs()
client = get_client()
if not client:
    client = Client(**client_kwargs)
client.activation_method = "wrapper"
if not client.config.debug and client.config.instrument and client.config.enabled:
    elasticapm.instrument()


class LambdaError(Exception):
    pass


def lambda_handler(event, context):
    """
    This handler is designed to replace the default handler in the lambda
    function, and then call the actual handler, which will be stored in
    ELASTICAPM_ORIGINAL_HANDLER.
    """
    # Prep original handler
    original_handler = os.environ.get("ELASTICAPM_ORIGINAL_HANDLER", None)
    if not original_handler:
        raise LambdaError("Cannot find original handler. ELASTICAPM_ORIGINAL_HANDLER is not set correctly.")
    try:
        module, handler = original_handler.rsplit(".", 1)
    except ValueError:
        raise LambdaError(f"ELASTICAPM_ORIGINAL_HANDLER is not set correctly: {original_handler}")

    # Import handler
    module = import_module(module.replace("/", "."))
    wrapped = getattr(module, handler)

    client = get_client()

    # Run the handler
    if not client.config.debug and client.config.instrument and client.config.enabled:
        with _lambda_transaction(wrapped, None, client, event, context) as sls:
            sls.response = wrapped(event, context)
            return sls.response
    else:
        return wrapped(event, context)
