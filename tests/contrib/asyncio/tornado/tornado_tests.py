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

import os

import mock

import elasticapm
from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.tornado import ElasticAPM
from elasticapm.utils.disttracing import TraceParent

pytestmark = pytest.mark.tornado


@pytest.fixture
def app(elasticapm_client):
    class HelloHandler(tornado.web.RequestHandler):
        def get(self):
            with async_capture_span("test"):
                pass
            return self.write("Hello, world")

        post = get

    class RenderHandler(tornado.web.RequestHandler):
        def get(self):
            with async_capture_span("test"):
                pass
            items = ["Item 1", "Item 2", "Item 3"]
            return self.render("test.html", title="Testing so hard", items=items)

    class BoomHandler(tornado.web.RequestHandler):
        def get(self):
            raise tornado.web.HTTPError()

        post = get

    app = tornado.web.Application(
        [(r"/", HelloHandler), (r"/boom", BoomHandler), (r"/render", RenderHandler)],
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
    )
    apm = ElasticAPM(app, elasticapm_client)
    yield app
    elasticapm.uninstrument()


@pytest.fixture
def app_no_client():
    class HelloHandler(tornado.web.RequestHandler):
        def get(self):
            with async_capture_span("test"):
                pass
            return self.write("Hello, world")

        post = get

    class RenderHandler(tornado.web.RequestHandler):
        def get(self):
            with async_capture_span("test"):
                pass
            items = ["Item 1", "Item 2", "Item 3"]
            return self.render("test.html", title="Testing so hard", items=items)

    class BoomHandler(tornado.web.RequestHandler):
        def get(self):
            raise tornado.web.HTTPError()

        post = get

    app = tornado.web.Application(
        [(r"/", HelloHandler), (r"/boom", BoomHandler), (r"/render", RenderHandler)],
        template_path=os.path.join(os.path.dirname(__file__), "templates"),
    )
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
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}

    assert span["name"] == "test"


@pytest.mark.gen_test
async def test_exception(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    with pytest.raises(tornado.httpclient.HTTPClientError):
        response = await http_client.fetch(base_url + "/boom")

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET BoomHandler"
    assert transaction["result"] == "HTTP 5xx"
    assert transaction["outcome"] == "failure"
    assert transaction["type"] == "request"
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}
    assert transaction["context"]["response"]["status_code"] == 500

    assert len(elasticapm_client.events[constants.ERROR]) == 1
    error = elasticapm_client.events[constants.ERROR][0]
    assert error["transaction_id"] == transaction["id"]
    assert error["exception"]["type"] == "HTTPError"
    assert error["context"]["request"] == transaction["context"]["request"]


@pytest.mark.gen_test
async def test_traceparent_handling(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    with mock.patch(
        "elasticapm.instrumentation.packages.tornado.TraceParent.from_headers", wraps=TraceParent.from_headers
    ) as wrapped_from_string:
        headers = tornado.httputil.HTTPHeaders()
        headers.add(constants.TRACEPARENT_HEADER_NAME, "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03")
        headers.add(constants.TRACESTATE_HEADER_NAME, "foo=bar,bar=baz")
        headers.add(constants.TRACESTATE_HEADER_NAME, "baz=bazzinga")
        request = tornado.httpclient.HTTPRequest(url=base_url, headers=headers)
        resp = await http_client.fetch(request)

    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert transaction["parent_id"] == "b7ad6b7169203331"
    assert "foo=bar,bar=baz,baz=bazzinga" == wrapped_from_string.call_args[0][0]["TraceState"]


@pytest.mark.gen_test
async def test_render(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    response = await http_client.fetch(base_url + "/render")
    assert response.code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 2

    assert transaction["name"] == "GET RenderHandler"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 2
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}

    span = spans[0]
    assert span["name"] == "test"
    span = spans[1]
    assert span["name"] == "test.html"
    assert span["action"] == "render"
    assert span["type"] == "template"


@pytest.mark.gen_test
async def test_capture_headers_body_is_dynamic(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    for i, val in enumerate((True, False)):
        elasticapm_client.config.update(str(i), capture_body="transaction" if val else "none", capture_headers=val)
        await http_client.fetch(base_url, method="POST", body=b"xyz")

        elasticapm_client.config.update(str(i) + str(i), capture_body="error" if val else "none", capture_headers=val)
        with pytest.raises(tornado.httpclient.HTTPClientError):
            await http_client.fetch(base_url + "/boom", method="POST", body=b"xyz")

    transactions = elasticapm_client.events[constants.TRANSACTION]
    errors = elasticapm_client.events[constants.ERROR]

    assert "headers" in transactions[0]["context"]["request"]
    assert transactions[0]["context"]["request"]["body"] == "xyz"
    assert "headers" in transactions[0]["context"]["response"]
    assert "headers" in errors[0]["context"]["request"]
    assert errors[0]["context"]["request"]["body"] == "xyz"

    assert "headers" not in transactions[2]["context"]["request"]
    assert "headers" not in transactions[2]["context"]["response"]
    assert transactions[2]["context"]["request"]["body"] == "[REDACTED]"
    assert "headers" not in errors[1]["context"]["request"]
    assert errors[1]["context"]["request"]["body"] == "[REDACTED]"


@pytest.mark.gen_test
async def test_no_elasticapm_client(app_no_client, base_url, http_client, elasticapm_client):
    """
    Need to make sure instrumentation works even when tornado is not
    explicitly using the agent
    """
    elasticapm_client.begin_transaction("test")
    response = await http_client.fetch(base_url)
    assert response.code == 200
    elasticapm_client.end_transaction("test")


@pytest.mark.gen_test
async def test_tornado_transaction_ignore_urls(app, base_url, http_client):
    elasticapm_client = app.elasticapm_client
    response = await http_client.fetch(base_url + "/render")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1

    elasticapm_client.config.update(1, transaction_ignore_urls="/*ender,/bla")

    response = await http_client.fetch(base_url + "/render")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
