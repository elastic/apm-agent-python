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

import pytest  # isort:skip

pytest.importorskip("starlette")  # isort:skip

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.starlette import ElasticAPM


def test_starlette_app_instrumented(wrapper_instrument, elasticapm_client):
    async def hi(request):
        body = await request.body()
        with async_capture_span("test"):
            pass
        return PlainTextResponse(str(len(body)))

    routes = [Route("/", hi)]
    app = Starlette(routes=routes)
    test_client = TestClient(app)

    app.build_middleware_stack()
    assert any(middleware.cls is ElasticAPM for middleware in app.user_middleware)
    test_client.get("/")
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
