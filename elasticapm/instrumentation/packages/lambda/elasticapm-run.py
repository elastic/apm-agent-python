#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import shutil
import sys


class LambdaError(Exception):
    pass


if __name__ == "__main__":
    original_handler = os.environ.get("_HANDLER", None)
    if not original_handler:
        raise LambdaError("Cannot find original handler. _HANDLER is not set correctly.")

    # AWS Lambda's `/var/runtime/bootstrap.py` uses `imp.load_module` to load
    # the handler from "_HANDLER". This means that the handler will be reloaded
    # (even if it's already been loaded), and any instrumentation that we do
    # will be lost. Thus, we can't use our normal wrapper script, and must
    # replace the handler altogether and wrap it manually.
    os.environ["ELASTICAPM_ORIGINAL_HANDLER"] = original_handler
    os.environ["_HANDLER"] = "elasticapm_handler.lambda_handler"

    # Invoke the runtime
    args = sys.argv[1:]
    runtime = shutil.which(args[0])
    args = args[1:]
    os.execl(runtime, runtime, *args)
