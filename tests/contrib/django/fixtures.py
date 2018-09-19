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
