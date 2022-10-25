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

from shutil import ExecError

from tests.fixtures import TempStoreClient

import pytest  # isort:skip


starlette = pytest.importorskip("starlette")  # isort:skip

import os

import mock
import urllib3
import wrapt
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

import elasticapm
from elasticapm import async_capture_span
from elasticapm.conf import constants
from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from elasticapm.utils.disttracing import TraceParent

pytestmark = [pytest.mark.starlette]

starlette_version_tuple = tuple(map(int, starlette.__version__.split(".")[:3]))

file_path, file_name = os.path.split(__file__)


@pytest.fixture
def app(elasticapm_client):
    app = Starlette()
    sub = Starlette()
    subsub = Starlette()
    app.mount("/sub", sub)
    sub.mount("/subsub", subsub)

    @app.exception_handler(Exception)
    async def handle_exception(request, exc):
        transaction_id = elasticapm.get_transaction_id()
        exc.transaction_id = transaction_id
        return PlainTextResponse(f"{transaction_id}", status_code=500)

    @app.route("/", methods=["GET", "POST"])
    async def hi(request):
        body = await request.body()
        with async_capture_span("test"):
            pass
        return PlainTextResponse(str(len(body)))

    @app.route("/hi/{name}", methods=["GET"])
    async def hi_name(request):
        name = request.path_params["name"]
        return PlainTextResponse("Hi {}".format(name))

    @app.route("/hello", methods=["GET", "POST"])
    async def hello(request):
        with async_capture_span("test"):
            pass
        return PlainTextResponse("ok")

    @app.route("/raise-exception", methods=["GET", "POST"])
    async def raise_exception(request):
        await request.body()
        raise ValueError()

    @app.route("/raise-base-exception", methods=["GET", "POST"])
    async def raise_base_exception(request):
        await request.body()
        raise Exception()

    @app.route("/hi/{name}/with/slash/", methods=["GET", "POST"])
    async def with_slash(request):
        return PlainTextResponse("Hi {}".format(request.path_params["name"]))

    @app.route("/hi/{name}/without/slash", methods=["GET", "POST"])
    async def without_slash(request):
        return PlainTextResponse("Hi {}".format(request.path_params["name"]))

    @sub.route("/hi")
    async def hi_from_sub(request):
        return PlainTextResponse("sub")

    @subsub.route("/hihi/{name}")
    async def hi_from_sub(request):
        return PlainTextResponse(request.path_params["name"])

    @app.websocket_route("/ws")
    async def ws(websocket):
        await websocket.accept()
        await websocket.send_text("Hello, world!")
        await websocket.close()

    app.add_middleware(ElasticAPM, client=elasticapm_client)

    yield app

    elasticapm.uninstrument()


def test_get(app, elasticapm_client):
    client = TestClient(app)

    response = client.get(
        "/",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "GET /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}

    response = transaction["context"]["response"]
    assert response["status_code"] == 200
    assert response["headers"]["content-type"] == "text/plain; charset=utf-8"

    assert span["name"] == "test"


@pytest.mark.parametrize("elasticapm_client", [{"capture_body": "all"}], indirect=True)
def test_post(app, elasticapm_client):
    client = TestClient(app)

    response = client.post(
        "/",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
        data={"foo": "bar"},
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 1
    span = spans[0]

    assert transaction["name"] == "POST /"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 1
    request = transaction["context"]["request"]
    assert request["method"] == "POST"
    assert request["socket"] == {"remote_address": "127.0.0.1"}
    assert request["body"] == "foo=bar"

    assert span["name"] == "test"


def test_exception(app, elasticapm_client):
    client = TestClient(app)

    with pytest.raises(ValueError):
        client.get(
            "/raise-exception",
            headers={
                constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
                constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
                "REMOTE_ADDR": "127.0.0.1",
            },
        )

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /raise-exception"
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
    assert error["exception"]["type"] == "ValueError"
    assert error["context"]["request"] == transaction["context"]["request"]


@pytest.mark.parametrize("header_name", [constants.TRACEPARENT_HEADER_NAME, constants.TRACEPARENT_LEGACY_HEADER_NAME])
def test_traceparent_handling(app, elasticapm_client, header_name):
    client = TestClient(app)
    with mock.patch(
        "elasticapm.contrib.starlette.TraceParent.from_string", wraps=TraceParent.from_string
    ) as wrapped_from_string:
        response = client.get(
            "/",
            headers={
                header_name: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
                constants.TRACESTATE_HEADER_NAME: "foo=bar,baz=bazzinga",
            },
        )

    assert response.status_code == 200

    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert transaction["parent_id"] == "b7ad6b7169203331"
    assert "foo=bar,baz=bazzinga" in wrapped_from_string.call_args[0]


def test_capture_headers_body_is_dynamic(app, elasticapm_client):
    client = TestClient(app)

    for i, val in enumerate((True, False)):
        elasticapm_client.config.update(str(i), capture_body="transaction" if val else "none", capture_headers=val)
        try:
            client.post("/", content="somedata", headers={"foo": "bar"})
        except TypeError:  # starlette < 0.21.0 used requests as base for TestClient, with a different API
            client.post("/", "somedata", headers={"foo": "bar"})

        elasticapm_client.config.update(str(i) + str(i), capture_body="error" if val else "none", capture_headers=val)
        with pytest.raises(ValueError):
            try:
                client.post("/raise-exception", content="somedata", headers={"foo": "bar"})
            except TypeError:
                client.post("/raise-exception", "somedata", headers={"foo": "bar"})

    assert "headers" in elasticapm_client.events[constants.TRANSACTION][0]["context"]["request"]
    assert "headers" in elasticapm_client.events[constants.TRANSACTION][0]["context"]["response"]
    assert elasticapm_client.events[constants.TRANSACTION][0]["context"]["request"]["body"] == "somedata"
    assert "headers" in elasticapm_client.events[constants.ERROR][0]["context"]["request"]
    assert elasticapm_client.events[constants.ERROR][0]["context"]["request"]["body"] == "somedata"

    assert "headers" not in elasticapm_client.events[constants.TRANSACTION][2]["context"]["request"]
    assert "headers" not in elasticapm_client.events[constants.TRANSACTION][2]["context"]["response"]
    assert elasticapm_client.events[constants.TRANSACTION][2]["context"]["request"]["body"] == "[REDACTED]"
    assert "headers" not in elasticapm_client.events[constants.ERROR][1]["context"]["request"]
    assert elasticapm_client.events[constants.ERROR][1]["context"]["request"]["body"] == "[REDACTED]"


def test_starlette_transaction_ignore_urls(app, elasticapm_client):
    client = TestClient(app)
    response = client.get("/hello")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1

    elasticapm_client.config.update(1, transaction_ignore_urls="/*ello,/world")
    response = client.get("/hello")
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1


def test_transaction_name_is_route(app, elasticapm_client):
    client = TestClient(app)

    response = client.get("/hi/shay")

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /hi/{name}"
    assert transaction["context"]["request"]["url"]["pathname"] == "/hi/shay"


@pytest.mark.skipif(starlette_version_tuple < (0, 14), reason="trailing slash behaviour new in 0.14")
@pytest.mark.parametrize(
    "url,expected",
    (
        ("/hi/shay/with/slash", "GET /hi/{name}/with/slash"),
        ("/hi/shay/without/slash/", "GET /hi/{name}/without/slash/"),
        ("/sub/subsub/hihi/shay/", "GET /sub/subsub/hihi/{name}/"),
    ),
)
def test_trailing_slash_redirect_detection(app, elasticapm_client, url, expected):
    client = TestClient(app)
    response = client.get(url, allow_redirects=False)
    assert response.status_code == 307
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    for transaction in elasticapm_client.events[constants.TRANSACTION]:
        assert transaction["name"] == expected


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"enabled": False},
    ],
    indirect=True,
)
def test_enabled_instrumentation(app, elasticapm_client):
    client = TestClient(app)

    assert not isinstance(urllib3.connectionpool.HTTPConnectionPool.urlopen, wrapt.BoundFunctionWrapper)


def test_transaction_name_is_route_for_mounts(app, elasticapm_client):
    """
    Tests if recursive URL matching works when apps are mounted in other apps
    """
    client = TestClient(app)
    response = client.get("/sub/hi")
    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /sub/hi"
    assert transaction["context"]["request"]["url"]["pathname"] == "/sub/hi"

    response = client.get("/sub/subsub/hihi/shay")
    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 2
    transaction = elasticapm_client.events[constants.TRANSACTION][1]
    assert transaction["name"] == "GET /sub/subsub/hihi/{name}"
    assert transaction["context"]["request"]["url"]["pathname"] == "/sub/subsub/hihi/shay"


def test_undefined_route(app, elasticapm_client):
    client = TestClient(app)

    response = client.get("/undefined")

    assert response.status_code == 404
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /undefined"


def test_undefined_mounted_route(app, elasticapm_client):
    client = TestClient(app)

    response = client.get("/sub/subsub/undefined")

    assert response.status_code == 404
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /sub/subsub/undefined"


@pytest.mark.parametrize(
    "elasticapm_client",
    [
        {"capture_body": "error"},
    ],
    indirect=True,
)
def test_capture_body_error(app, elasticapm_client):
    """
    Context: https://github.com/elastic/apm-agent-python/issues/1032

    Before the above issue was fixed, this test would hang
    """
    client = TestClient(app)
    with pytest.raises(ValueError):
        response = client.post("/raise-exception", data="[0, 1]")


@pytest.fixture
def app_static_files_only(elasticapm_client):
    app = Starlette()
    app.add_middleware(ElasticAPM, client=elasticapm_client)
    app.mount("/tmp", StaticFiles(directory=file_path), name="static")

    yield app

    elasticapm.uninstrument()


def test_static_files_only(app_static_files_only, elasticapm_client):
    client = TestClient(app_static_files_only)

    response = client.get(
        "/tmp/" + file_name,
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /tmp"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 0
    assert transaction["context"]["request"]["url"]["pathname"] == "/tmp/" + file_name
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}


def test_non_utf_8_body_in_ignored_paths_with_capture_body(app, elasticapm_client):
    client = TestClient(app)
    elasticapm_client.config.update(1, capture_body="all", transaction_ignore_urls="/hello")
    response = client.post("/hello", data=b"b$\x19\xc2")
    assert response.status_code == 200
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 0


@pytest.mark.parametrize("elasticapm_client", [{"capture_body": "all"}], indirect=True)
def test_long_body(app, elasticapm_client):
    client = TestClient(app)

    response = client.post(
        "/",
        data={"foo": "b" * 10000},
    )

    assert response.status_code == 200

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    request = transaction["context"]["request"]
    assert request["body"] == "foo=" + "b" * 9993 + "..."
    assert response.text == "10004"


def test_static_files_only_file_notfound(app_static_files_only, elasticapm_client):
    client = TestClient(app_static_files_only)

    response = client.get(
        "/tmp/whatever",
        headers={
            constants.TRACEPARENT_HEADER_NAME: "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-03",
            constants.TRACESTATE_HEADER_NAME: "foo=bar,bar=baz",
            "REMOTE_ADDR": "127.0.0.1",
        },
    )

    assert response.status_code == 404

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    spans = elasticapm_client.spans_for_transaction(transaction)
    assert len(spans) == 0

    assert transaction["name"] == "GET /tmp"
    assert transaction["result"] == "HTTP 4xx"
    assert transaction["outcome"] == "success"
    assert transaction["type"] == "request"
    assert transaction["span_count"]["started"] == 0
    assert transaction["context"]["request"]["url"]["pathname"] == "/tmp/whatever"
    request = transaction["context"]["request"]
    assert request["method"] == "GET"
    assert request["socket"] == {"remote_address": "127.0.0.1"}


def test_make_client_with_config():
    c = make_apm_client(config={"SERVICE_NAME": "foo"}, client_cls=TempStoreClient)
    c.close()
    assert c.config.service_name == "foo"


def test_make_client_without_config():
    with mock.patch.dict("os.environ", {"ELASTIC_APM_SERVICE_NAME": "foo"}):
        c = make_apm_client(client_cls=TempStoreClient)
        c.close()
        assert c.config.service_name == "foo"


def test_websocket(app, elasticapm_client):
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        data = websocket.receive_text()
        assert data == "Hello, world!"

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 0


def test_transaction_active_in_base_exception_handler(app, elasticapm_client):
    client = TestClient(app)
    try:
        response = client.get("/raise-base-exception")
    except Exception as exc:
        # This is set by the exception handler -- we want to make sure the
        # handler has access to the transaction.
        assert exc.transaction_id

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
