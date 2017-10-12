import pytest

from elasticapm.base import Client


@pytest.fixture()
def elasticapm_client(request):
    client_config = getattr(request, 'param', {})
    app_name = client_config.pop('app_name', 'myapp')
    secret_token = client_config.pop('secret_token', 'test_key')
    client = TempStoreClient(app_name=app_name, secret_token=secret_token, **client_config)
    yield client
    client.close()


class TempStoreClient(Client):
    def __init__(self, **defaults):
        self.events = []
        super(TempStoreClient, self).__init__(**defaults)

    def send(self, **kwargs):
        self.events.append(kwargs)
