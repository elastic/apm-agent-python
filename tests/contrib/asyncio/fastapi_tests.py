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

from tests.fixtures import TempStoreClient

import pytest  # isort:skip

fastapi = pytest.importorskip("fastapi")  # isort:skip

from fastapi import APIRouter, FastAPI
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import elasticapm
from elasticapm.conf import constants
from elasticapm.contrib.starlette import ElasticAPM, make_apm_client

pytestmark = [pytest.mark.starlette]


@pytest.fixture
def fastapi_app(elasticapm_client):
    router = APIRouter(prefix="/api")

    @router.get("/items/{item_id}")
    async def get_item(item_id: int):
        return {"item_id": item_id}

    app = FastAPI()
    app.include_router(router)
    app.add_middleware(ElasticAPM, client=elasticapm_client)

    yield app

    elasticapm.uninstrument()


def test_included_router_request_succeeds(fastapi_app, elasticapm_client):
    client = TestClient(fastapi_app)

    response = client.get("/api/items/42")

    assert response.status_code == 200
    assert response.json() == {"item_id": 42}
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1


def test_included_router_transaction_name(fastapi_app, elasticapm_client):
    client = TestClient(fastapi_app)

    response = client.get("/api/items/42")

    assert response.status_code == 200

    transaction = elasticapm_client.events[constants.TRANSACTION][0]
    assert transaction["name"] == "GET /api/items/{item_id}"


def test_included_router_with_mounted_app_transaction_name(elasticapm_client):
    router = APIRouter(prefix="/api")

    @router.get("/items/{item_id}")
    async def get_item(item_id: int):
        return {"item_id": item_id}

    async def hi(request):
        return PlainTextResponse("sub")

    sub = Starlette(routes=[Route("/hi", hi)])
    app = FastAPI()
    app.include_router(router)
    app.mount("/sub", sub)
    app.add_middleware(ElasticAPM, client=elasticapm_client)
    client = TestClient(app)

    try:
        response = client.get("/sub/hi")

        assert response.status_code == 200
        assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
        transaction = elasticapm_client.events[constants.TRANSACTION][0]
        assert transaction["name"] == "GET /sub/hi"
    finally:
        elasticapm.uninstrument()


def test_included_router_options_partial_match(fastapi_app, elasticapm_client):
    client = TestClient(fastapi_app)

    response = client.options("/api/items/42")

    assert response.status_code == 405
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1


def test_make_client_with_fastapi_framework():
    c = make_apm_client(config={"SERVICE_NAME": "foo"}, client_cls=TempStoreClient, framework_name="fastapi")
    c.close()
    assert c.config.service_name == "foo"
