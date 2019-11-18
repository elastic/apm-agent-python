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
import asyncio

import aiohttp

import elasticapm
from elasticapm import Client

CLIENT_KEY = "_elasticapm_client_instance"


class ElasticAPM:
    def __init__(self, app):
        config = app.get("ELASTIC_APM", {})
        config.setdefault("framework_name", "aiohttp")
        config.setdefault("framework_version", aiohttp.__version__)
        client = Client(config=config)
        app[CLIENT_KEY] = client
        self.install_tracing(app)

    def install_tracing(self, app):
        from elasticapm.contrib.aiohttp.middleware import tracing_middleware

        app.middlewares.insert(0, tracing_middleware(app))
        app.on_response_prepare.append(on_response_prepare)


@asyncio.coroutine
def on_response_prepare(request, response):
    elasticapm_client = request.get(CLIENT_KEY)
    if elasticapm_client:
        elasticapm.set_transaction_result("HTTP {}xx".format(response.status // 100), override=False)
        resource = request.match_info.route.resource
        if resource:
            name = "{} {}".format(request.method, resource.canonical)
            elasticapm.set_transaction_name(name, override=False)
        elasticapm_client.end_transaction()
