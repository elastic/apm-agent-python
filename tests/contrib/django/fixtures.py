from django.apps import apps

import pytest

from elasticapm.contrib.django.apps import instrument, register_handlers
from elasticapm.contrib.django.client import DjangoClient


class TempStoreClient(DjangoClient):
    def __init__(self, *args, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(*args, **kwargs)

    def send(self, url, **kwargs):
        self.events.append(kwargs)


@pytest.fixture()
def django_elasticapm_client(request):
    client_config = getattr(request, 'param', {})
    client_config.setdefault('service_name', 'app')
    client_config.setdefault('secret_token', 'secret')
    client_config.setdefault('span_frames_min_duration_ms', -1)
    app = apps.get_app_config('elasticapm.contrib.django')
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
    validating_httpserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    client_config = getattr(request, 'param', {})
    client_config.setdefault('server_url', validating_httpserver.url)
    client_config.setdefault('service_name', 'app')
    client_config.setdefault('secret_token', 'secret')
    client_config.setdefault('transport_class', 'elasticapm.transport.http.Transport')
    client_config.setdefault('span_frames_min_duration_ms', -1)
    app = apps.get_app_config('elasticapm.contrib.django')
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
