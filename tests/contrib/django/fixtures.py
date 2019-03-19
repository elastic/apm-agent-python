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

from django.apps import apps

import pytest

from elasticapm.conf.constants import SPAN
from elasticapm.contrib.django.apps import instrument, register_handlers
from elasticapm.contrib.django.client import DjangoClient


class TempStoreClient(DjangoClient):
    def __init__(self, **inline):
        inline.setdefault("transport_class", "tests.fixtures.DummyTransport")
        super(TempStoreClient, self).__init__(**inline)

    @property
    def events(self):
        return self._transport.events

    def spans_for_transaction(self, transaction):
        """Test helper method to get all spans of a specific transaction"""
        return [span for span in self.events[SPAN] if span["transaction_id"] == transaction["id"]]


@pytest.fixture()
def django_elasticapm_client(request):
    client_config = getattr(request, "param", {})
    client_config.setdefault("service_name", "app")
    client_config.setdefault("secret_token", "secret")
    client_config.setdefault("span_frames_min_duration", -1)
    app = apps.get_app_config("elasticapm.contrib.django")
    old_client = app.client
    client = TempStoreClient(**client_config)
    register_handlers(client)
    instrument(client)
    app.client = client
    yield client
    client.close()

    app.client = old_client

    if old_client:
        register_handlers(old_client)
        instrument(old_client)


@pytest.fixture()
def django_sending_elasticapm_client(request, validating_httpserver):
    validating_httpserver.serve_content(code=202, content="", headers={"Location": "http://example.com/foo"})
    client_config = getattr(request, "param", {})
    client_config.setdefault("server_url", validating_httpserver.url)
    client_config.setdefault("service_name", "app")
    client_config.setdefault("secret_token", "secret")
    client_config.setdefault("transport_class", "elasticapm.transport.http.Transport")
    client_config.setdefault("span_frames_min_duration", -1)
    app = apps.get_app_config("elasticapm.contrib.django")
    old_client = app.client
    client = DjangoClient(**client_config)
    register_handlers(client)
    instrument(client)
    app.client = client
    client.httpserver = validating_httpserver
    yield client
    client.close()

    app.client = old_client

    if old_client:
        register_handlers(old_client)
        instrument(old_client)
