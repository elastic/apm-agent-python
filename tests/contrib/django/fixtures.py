from django.apps import apps

import pytest

from elasticapm.contrib.django.apps import instrument, register_handlers
from elasticapm.contrib.django.client import DjangoClient


class TempStoreClient(DjangoClient):
    def __init__(self, *args, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(*args, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)


@pytest.fixture()
def elasticapm_client():
    app = apps.get_app_config('elasticapm.contrib.django')
    old_client = app.client
    client = TempStoreClient()
    register_handlers(client)
    instrument(client)
    app.client = client
    yield client

    app.client = old_client

    if old_client:
        register_handlers(old_client)
        instrument(old_client)
