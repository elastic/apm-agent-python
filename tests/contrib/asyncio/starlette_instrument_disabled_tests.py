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

import pytest

pytest.importorskip("starlette")

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, StreamingResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import elasticapm
from elasticapm.conf import constants
from elasticapm.contrib.starlette import ElasticAPM

pytestmark = pytest.mark.starlette


@pytest.fixture(autouse=True)
def clean_instrumentation():
    elasticapm.uninstrument()
    yield
    elasticapm.uninstrument()


@pytest.mark.parametrize("framework", ["starlette", "fastapi"])
@pytest.mark.parametrize("instrument", [False, True])
@pytest.mark.parametrize("kind", ["success", "handled", "unhandled", "stream"])
def test_transaction_completion_without_library_instrumentation(elasticapm_client, instrument, kind, framework, mocker):
    elasticapm_client.config.update("1", instrument=instrument)
    handler_ids = []

    async def endpoint(request: Request):
        assert elasticapm.get_transaction_id()
        if kind in ("handled", "unhandled"):
            raise ValueError("test failure")
        if kind == "stream":
            completed = len(elasticapm_client.events[constants.TRANSACTION])

            async def chunks():
                for chunk in (b"a", b"b"):
                    assert elasticapm.get_transaction_id()
                    assert len(elasticapm_client.events[constants.TRANSACTION]) == completed
                    yield chunk

            return StreamingResponse(chunks())
        return PlainTextResponse("ok")

    async def error_handler(request, exc):
        handler_ids.append(elasticapm.get_transaction_id())
        elasticapm.label(error_handler="visited")
        return PlainTextResponse("handled", status_code=500)

    handlers = {Exception: error_handler} if kind == "handled" else {}
    if framework == "fastapi":
        app = pytest.importorskip("fastapi").FastAPI(exception_handlers=handlers)
        app.add_api_route("/", endpoint)
    else:
        app = Starlette(routes=[Route("/", endpoint)], exception_handlers=handlers)
    app.add_middleware(ElasticAPM, client=elasticapm_client)
    with TestClient(app, raise_server_exceptions=False) as client:
        end_transaction = mocker.spy(elasticapm_client, "end_transaction")
        for _ in range(2):
            response = client.get("/")
            assert response.status_code == (500 if kind in ("handled", "unhandled") else 200)
        assert end_transaction.call_count == 2
    transactions = elasticapm_client.events[constants.TRANSACTION]
    assert len(transactions) == 2
    assert transactions[0]["id"] != transactions[1]["id"]
    if kind == "handled":
        assert handler_ids == [transaction["id"] for transaction in transactions]
        assert all(t["context"]["tags"]["error_handler"] == "visited" for t in transactions)
    if kind in ("handled", "unhandled"):
        assert len(elasticapm_client.events[constants.ERROR]) == 2
    if kind == "stream":
        assert response.content == b"ab"


@pytest.mark.parametrize("elasticapm_client", [{"instrument": False}, {"instrument": True}], indirect=True)
def test_library_instrumentation_respects_instrument_setting(elasticapm_client):
    async def endpoint(request):
        await asyncio.tasks.sleep(0)
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", endpoint)])
    app.add_middleware(ElasticAPM, client=elasticapm_client)
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
    assert hasattr(asyncio.tasks.sleep, "__wrapped__") == elasticapm_client.config.instrument
    spans = elasticapm_client.events[constants.SPAN]
    assert [span["name"] for span in spans] == (["asyncio.sleep"] if elasticapm_client.config.instrument else [])
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1


@pytest.mark.parametrize("elasticapm_client", [{"instrument": False, "enabled": False}], indirect=True)
def test_disabled_agent_does_not_install_lifecycle_hook(elasticapm_client, mocker):
    instrument = mocker.patch("elasticapm.instrumentation.control.instrument")
    ElasticAPM(Starlette(), client=elasticapm_client)
    instrument.assert_not_called()
