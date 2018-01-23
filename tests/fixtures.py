import json
import random
import zlib

import jsonschema
import pytest
import requests
from pytest_localserver.http import ContentServer
from werkzeug.wrappers import Request, Response

from elasticapm.base import Client

ERRORS_SCHEMA = 'https://raw.githubusercontent.com/elastic/apm-server/master/docs/spec/errors/payload.json'
TRANSACTIONS_SCHEMA = 'https://raw.githubusercontent.com/elastic/apm-server/master/docs/spec/transactions/payload.json'

VALIDATORS = {
    '/v1/errors': jsonschema.Draft4Validator(
        requests.get(ERRORS_SCHEMA).json(),
        resolver=jsonschema.RefResolver(
            base_uri='/'.join(ERRORS_SCHEMA.split('/')[:-1]) + '/',
            referrer=ERRORS_SCHEMA,
        )
    ),
    '/v1/transactions': jsonschema.Draft4Validator(
        requests.get(TRANSACTIONS_SCHEMA).json(),
        resolver=jsonschema.RefResolver(
            base_uri='/'.join(TRANSACTIONS_SCHEMA.split('/')[:-1]) + '/',
            referrer=TRANSACTIONS_SCHEMA,
        )
    )
}


class ValidatingWSGIApp(ContentServer):
    def __init__(self, **kwargs):
        super(ValidatingWSGIApp, self).__init__(**kwargs)
        self.payloads = []
        self.responses = []
        self.skip_validate = False

    def __call__(self, environ, start_response):
        code = self.code
        content = self.content
        request = Request(environ)
        self.requests.append(request)
        data = request.data
        if request.content_encoding == 'deflate':
            data = zlib.decompress(data)
        data = data.decode(request.charset)
        if request.content_type == 'application/json':
            data = json.loads(data)
        self.payloads.append(data)
        validator = VALIDATORS.get(request.path, None)
        if validator and not self.skip_validate:
            try:
                validator.validate(data)
                code = 202
            except jsonschema.ValidationError as e:
                code = 400
                content = json.dumps({'status': 'error', 'message': str(e)})
        response = Response(status=code)
        response.headers.clear()
        response.headers.extend(self.headers)
        response.data = content
        self.responses.append({'code': code, 'content': content})
        return response(environ, start_response)


@pytest.fixture()
def elasticapm_client(request):
    client_config = getattr(request, 'param', {})
    client_config.setdefault('service_name', 'myapp')
    client_config.setdefault('secret_token', 'test_key')
    client_config.setdefault('include_paths', ('*/tests/*',))
    client_config.setdefault('span_frames_min_duration_ms', -1)
    client = TempStoreClient(**client_config)
    yield client
    client.close()


@pytest.fixture()
def validating_httpserver(request):
    server = ValidatingWSGIApp()
    server.start()
    request.addfinalizer(server.stop)
    return server


@pytest.fixture()
def sending_elasticapm_client(request, validating_httpserver):
    validating_httpserver.serve_content(code=202, content='', headers={'Location': 'http://example.com/foo'})
    client_config = getattr(request, 'param', {})
    client_config.setdefault('server_url', validating_httpserver.url)
    client_config.setdefault('service_name', 'myapp')
    client_config.setdefault('secret_token', 'test_key')
    client_config.setdefault('transport_class', 'elasticapm.transport.http.Transport')
    client_config.setdefault('span_frames_min_duration_ms', -1)
    client_config.setdefault('include_paths', ('*/tests/*',))
    client = Client(**client_config)
    client.httpserver = validating_httpserver
    yield client
    client.close()


class TempStoreClient(Client):
    def __init__(self, **defaults):
        self.events = []
        super(TempStoreClient, self).__init__(**defaults)

    def send(self, url, **kwargs):
        self.events.append(kwargs)


@pytest.fixture()
def not_so_random():
    old_state = random.getstate()
    random.seed(42)
    yield
    random.setstate(old_state)
