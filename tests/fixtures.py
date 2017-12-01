import pytest

from elasticapm.base import Client


@pytest.fixture()
def elasticapm_client(request):
    client_config = getattr(request, 'param', {})
    client_config.setdefault('app_name', 'myapp')
    client_config.setdefault('secret_token', 'test_key')
    client = TempStoreClient(**client_config)
    yield client
    client.close()


@pytest.fixture()
def sending_elasticapm_client(request, httpserver):
    httpserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    client_config = getattr(request, 'param', {})
    client_config.setdefault('server_url', httpserver.url)
    client_config.setdefault('app_name', 'myapp')
    client_config.setdefault('secret_token', 'test_key')
    client_config.setdefault('transport_class', 'elasticapm.transport.http.Transport')
    client = Client(**client_config)
    client.httpserver = httpserver
    yield client
    client.close()


class TempStoreClient(Client):
    def __init__(self, **defaults):
        self.events = []
        super(TempStoreClient, self).__init__(**defaults)

    def send(self, url, **kwargs):
        self.events.append(kwargs)
