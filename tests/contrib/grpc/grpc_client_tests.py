#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import itertools
import os
import subprocess
import sys
import time
import urllib.parse
from collections import defaultdict

import pytest

from tests.fixtures import get_free_port, wait_for_open_port

grpc = pytest.importorskip("grpc")

pytestmark = pytest.mark.grpc


from .grpc_app.testgrpc_pb2 import Message
from .grpc_app.testgrpc_pb2_grpc import TestServiceStub


def setup_env(request, validating_httpserver):
    config = getattr(request, "param", {})
    env = {f"ELASTIC_APM_{k.upper()}": str(v) for k, v in config.items()}
    env.setdefault("ELASTIC_APM_SERVER_URL", validating_httpserver.url)
    return env


def setup_grpc_server(env):
    free_port = get_free_port()
    server_proc = subprocess.Popen(
        [os.path.join(sys.prefix, "bin", "python"), "-m", "tests.contrib.grpc.grpc_app.server", str(free_port)],
        stdout=sys.stdout,
        stderr=sys.stdout,
        env=env,
    )
    wait_for_open_port(free_port)
    return server_proc, free_port


@pytest.fixture()
def env_fixture(validating_httpserver, request):
    env = setup_env(request, validating_httpserver)
    return env


if hasattr(grpc, "aio"):
    grpc_server_fixture_params = ["async", "sync"]
else:
    grpc_server_fixture_params = ["sync"]


@pytest.fixture(params=grpc_server_fixture_params)
def grpc_client_and_server_url(env_fixture, request):
    env = {k: v for k, v in env_fixture.items()}
    if request.param == "async":
        env["GRPC_SERVER_ASYNC"] = "1"
    server_proc, free_port = setup_grpc_server(env)
    server_addr = f"localhost:{free_port}"
    test_channel = grpc.insecure_channel(server_addr)
    test_client = TestServiceStub(test_channel)
    yield test_client, server_addr
    server_proc.terminate()


def test_grpc_client_server_instrumentation(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_server_host, grpc_server_port = grpc_server_url.split(":")
    sending_elasticapm_client.begin_transaction("request")
    parsed_url = urllib.parse.urlparse(sending_elasticapm_client.httpserver.url)
    response = grpc_client.GetServerResponse(Message(message="foo"))
    sending_elasticapm_client.end_transaction("grpc-test")
    sending_elasticapm_client.close()
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(1000):
        if len(sending_elasticapm_client.httpserver.payloads) > 2:
            break
        time.sleep(0.01)
    server_meta, server_transactions, server_spans, server_errors = extract_events_from_payload("grpc-server", payloads)
    client_meta, client_transactions, client_spans, client_errors = extract_events_from_payload("myapp", payloads)
    client_span = client_spans[0]
    assert len(server_errors) == 0

    assert client_span["trace_id"] == client_transactions[0]["trace_id"] == server_transactions[0]["trace_id"]

    assert server_transactions[0]["name"] == "/test.TestService/GetServerResponse"
    assert server_transactions[0]["outcome"] == "success"
    assert server_meta["service"]["framework"]["name"] == "grpc"
    assert server_meta["service"]["framework"]["version"] == grpc.__version__

    assert client_span["id"] == server_transactions[0]["parent_id"]
    assert client_span["name"] == "/test.TestService/GetServerResponse"
    assert client_span["type"] == "external"
    assert client_span["subtype"] == "grpc"
    assert client_span["context"]["destination"]["address"] == grpc_server_host
    assert client_span["context"]["destination"]["port"] == int(grpc_server_port)
    assert client_span["context"]["destination"]["service"]["resource"] == f"{grpc_server_host}:{grpc_server_port}"


def test_grpc_client_server_abort(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_server_host, grpc_server_port = grpc_server_url.split(":")
    sending_elasticapm_client.begin_transaction("request")
    parsed_url = urllib.parse.urlparse(sending_elasticapm_client.httpserver.url)
    with pytest.raises(Exception):
        response = grpc_client.GetServerResponseAbort(Message(message="foo"))
    sending_elasticapm_client.end_transaction("grpc-test")
    sending_elasticapm_client.close()
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(1000):
        if len(sending_elasticapm_client.httpserver.payloads) > 3:
            break
        time.sleep(0.01)
    server_meta, server_transactions, server_spans, server_errors = extract_events_from_payload("grpc-server", payloads)
    client_meta, client_transactions, client_spans, client_errors = extract_events_from_payload("myapp", payloads)
    client_span = client_spans[0]
    assert len(server_errors) == 1

    assert client_span["trace_id"] == client_transactions[0]["trace_id"] == server_transactions[0]["trace_id"]

    assert server_transactions[0]["name"] == "/test.TestService/GetServerResponseAbort"
    assert server_transactions[0]["outcome"] == "failure"

    assert client_span["id"] == server_transactions[0]["parent_id"]
    assert client_span["name"] == "/test.TestService/GetServerResponseAbort"


def test_grpc_client_server_status(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_server_host, grpc_server_port = grpc_server_url.split(":")
    sending_elasticapm_client.begin_transaction("request")
    parsed_url = urllib.parse.urlparse(sending_elasticapm_client.httpserver.url)
    with pytest.raises(Exception):
        response = grpc_client.GetServerResponseUnavailable(Message(message="foo"))
    sending_elasticapm_client.end_transaction("grpc-test")
    sending_elasticapm_client.close()
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(1000):
        if len(sending_elasticapm_client.httpserver.payloads) > 2:
            break
        time.sleep(0.01)
    server_meta, server_transactions, server_spans, server_errors = extract_events_from_payload("grpc-server", payloads)
    client_meta, client_transactions, client_spans, client_errors = extract_events_from_payload("myapp", payloads)
    client_span = client_spans[0]
    assert len(server_errors) == 0

    assert client_span["trace_id"] == client_transactions[0]["trace_id"] == server_transactions[0]["trace_id"]
    assert server_transactions[0]["outcome"] == "failure"
    assert client_span["id"] == server_transactions[0]["parent_id"]

    assert client_span["name"] == "/test.TestService/GetServerResponseUnavailable"


def test_grpc_client_server_exception(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_server_host, grpc_server_port = grpc_server_url.split(":")
    sending_elasticapm_client.begin_transaction("request")
    parsed_url = urllib.parse.urlparse(sending_elasticapm_client.httpserver.url)
    with pytest.raises(Exception):
        response = grpc_client.GetServerResponseException(Message(message="foo"))
    sending_elasticapm_client.end_transaction("grpc-test")
    sending_elasticapm_client.close()
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(1000):
        if len(sending_elasticapm_client.httpserver.payloads) > 3:
            break
        time.sleep(0.01)
    server_meta, server_transactions, server_spans, server_errors = extract_events_from_payload("grpc-server", payloads)
    assert len(server_errors) == 1
    error = server_errors[0]
    assert error["transaction_id"] == server_transactions[0]["id"]


def test_grpc_client_unsampled_span(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_server_host, grpc_server_port = grpc_server_url.split(":")
    transaction = sending_elasticapm_client.begin_transaction("request")
    transaction.is_sampled = False
    parsed_url = urllib.parse.urlparse(sending_elasticapm_client.httpserver.url)
    response = grpc_client.GetServerResponse(Message(message="foo"))
    transaction.is_sampled = True
    sending_elasticapm_client.end_transaction("grpc-test")
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(1000):
        if len(sending_elasticapm_client.httpserver.payloads) > 1:
            break
        time.sleep(0.01)
    transaction_data = payloads[1][1]["transaction"]
    assert transaction_data["span_count"]["started"] == 0


@pytest.mark.parametrize(
    "env_fixture",
    [
        {
            "recording": "False",
        }
    ],
    indirect=True,
)
def test_grpc_client_unsampled_transaction(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, grpc_server_url = grpc_client_and_server_url
    grpc_client.GetServerResponse(Message(message="foo"))
    payloads = sending_elasticapm_client.httpserver.payloads
    for i in range(100):
        if len(sending_elasticapm_client.httpserver.payloads) > 1:
            break
        time.sleep(0.01)
    assert len(payloads) == 1  # only the server_version request


@pytest.mark.parametrize("sending_elasticapm_client", [{"transaction_max_spans": 1}], indirect=True)
def test_grpc_client_max_spans(instrument, sending_elasticapm_client, grpc_client_and_server_url):
    grpc_client, _ = grpc_client_and_server_url
    transaction = sending_elasticapm_client.begin_transaction("request")
    _ = grpc_client.GetServerResponse(Message(message="foo"))
    _ = grpc_client.GetServerResponse(Message(message="bar"))
    sending_elasticapm_client.end_transaction("grpc-test")
    assert transaction.dropped_spans == 1


def extract_events_from_payload(service_name, payloads):
    payloads = [
        payload for payload in payloads if payload and payload[0]["metadata"]["service"]["name"] == service_name
    ]
    events = defaultdict(list)
    for event in itertools.chain(*payloads):
        for k, v in event.items():
            events[k].append(v)
    return events["metadata"][0], events["transaction"], events["span"], events["error"]
