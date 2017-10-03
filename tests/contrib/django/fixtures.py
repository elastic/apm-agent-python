import pytest

from elasticapm.contrib.django.client import DjangoClient
from elasticapm.contrib.django.apps import register_handlers, instrument


class TempStoreClient(DjangoClient):
    def __init__(self, *args, **kwargs):
        self.events = []
        super(TempStoreClient, self).__init__(*args, **kwargs)

    def send(self, **kwargs):
        self.events.append(kwargs)


@pytest.fixture()
def elasticapm_client():
    client = TempStoreClient()
    register_handlers(client)
    instrument(client)
    yield client
