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

import pytest  # isort:skip

tornado = pytest.importorskip("tornado")  # isort:skip

import mock

from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.tornado import ElasticAPM


@pytest.fixture
def app(elasticapm_client):
    class HelloHandler(tornado.web.RequestHandler):
        def get(self):
            with async_capture_span("test"):
                pass
            return self.write("Hello, world")

    class BoomHandler(tornado.web.RequestHandler):
        def get(self):
            raise ValueError()

    app = tornado.web.Application([(r"/", HelloHandler), (r"/boom", BoomHandler)])
    apm = ElasticAPM(app, elasticapm_client)
    return app


@pytest.mark.gen_test
async def test_get(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    response = await http_client.fetch(base_url)
    assert response.code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "GET HelloHandler"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    request["method"] == "GET"
    request["socket"] == {"remote_address": "127.0.0.1", "encrypted": False}

    assert span["name"] == "test"
