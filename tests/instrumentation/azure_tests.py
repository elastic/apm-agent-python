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


import os
import uuid

import pytest

from elasticapm.conf import constants

azureblob = pytest.importorskip("azure.storage.blob")
azurequeue = pytest.importorskip("azure.storage.queue")
azurequeue = pytest.importorskip("azure.cosmosdb.table")
pytestmark = [pytest.mark.azurestorage]

from azure.cosmosdb.table.tableservice import TableService
from azure.storage.blob import BlobServiceClient
from azure.storage.queue import QueueClient

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

if not CONNECTION_STRING:
    pytestmark.append(
        pytest.mark.skip("Skipping azure storage tests, no AZURE_STORAGE_CONNECTION_STRING environment variable set")
    )


@pytest.fixture()
def container_client(blob_service_client):
    container_name = "apm-agent-python-ci-" + str(uuid.uuid4())
    container_client = blob_service_client.create_container(container_name)

    yield container_client

    blob_service_client.delete_container(container_name)


@pytest.fixture()
def blob_service_client():
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    return blob_service_client


@pytest.fixture()
def queue_client():
    queue_name = "apm-agent-python-ci-" + str(uuid.uuid4())
    queue_client = QueueClient.from_connection_string(CONNECTION_STRING, queue_name)
    queue_client.create_queue()

    yield queue_client

    queue_client.delete_queue()


@pytest.fixture()
def table_service():
    table_name = "apm-agent-python-ci-" + str(uuid.uuid4())
    table_service = TableService(connection_string=CONNECTION_STRING)
    table_service.create_table(table_name)
    table_service.table_name = table_name

    yield table_service

    table_service.delete_table(table_name)


def test_blob_list_blobs(instrument, elasticapm_client, container_client):
    elasticapm_client.begin_transaction("transaction.test")
    list(container_client.list_blobs())
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "AzureBlob ListBlobs {}".format(container_client.container_name)
    assert span["type"] == "storage"
    assert span["subtype"] == "azureblob"
    assert span["action"] == "ListBlobs"


def test_blob_create_container(instrument, elasticapm_client, blob_service_client):
    elasticapm_client.begin_transaction("transaction.test")
    container_name = str(uuid.uuid4())
    container_client = blob_service_client.create_container(container_name)
    blob_service_client.delete_container(container_name)
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "AzureBlob Create {}".format(container_name)
    assert span["type"] == "storage"
    assert span["subtype"] == "azureblob"
    assert span["action"] == "Create"


def test_blob_upload(instrument, elasticapm_client, container_client, blob_service_client):
    elasticapm_client.begin_transaction("transaction.test")
    # Upload this file to the container
    blob_client = blob_service_client.get_blob_client(container=container_client.container_name, blob=__file__)
    with open(__file__, "rb") as data:
        blob_client.upload_blob(data)
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "AzureBlob Upload {}/{}".format(container_client.container_name, __file__)
    assert span["type"] == "storage"
    assert span["subtype"] == "azureblob"
    assert span["action"] == "Upload"


def test_queue(instrument, elasticapm_client, queue_client):
    elasticapm_client.begin_transaction("transaction.test")
    # Send a message
    queue_client.send_message("Test message")
    list(queue_client.peek_messages())
    messages = queue_client.receive_messages()
    for msg_batch in messages.by_page():
        for msg in msg_batch:
            queue_client.delete_message(msg)
    elasticapm_client.end_transaction("MyView")

    span = elasticapm_client.events[constants.SPAN][0]
    assert span["name"] == "AzureQueue SEND to {}".format(queue_client.queue_name)
    assert span["type"] == "messaging"
    assert span["subtype"] == "azurequeue"
    assert span["action"] == "send"

    span = elasticapm_client.events[constants.SPAN][1]
    assert span["name"] == "AzureQueue PEEK from {}".format(queue_client.queue_name)
    assert span["type"] == "messaging"
    assert span["subtype"] == "azurequeue"
    assert span["action"] == "peek"

    span = elasticapm_client.events[constants.SPAN][2]
    assert span["name"] == "AzureQueue RECEIVE from {}".format(queue_client.queue_name)
    assert span["type"] == "messaging"
    assert span["subtype"] == "azurequeue"
    assert span["action"] == "receive"

    span = elasticapm_client.events[constants.SPAN][3]
    assert span["name"] == "AzureQueue DELETE from {}".format(queue_client.queue_name)
    assert span["type"] == "messaging"
    assert span["subtype"] == "azurequeue"
    assert span["action"] == "delete"


def test_table_create(instrument, elasticapm_client):
    table_name = "apmagentpythonci" + str(uuid.uuid4().hex)
    table_service = TableService(connection_string=CONNECTION_STRING)

    elasticapm_client.begin_transaction("transaction.test")
    table_service.create_table(table_name)
    table_service.delete_table(table_name)
    elasticapm_client.end_transaction("MyView")

    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "AzureTable Create {}".format(table_name)
    assert span["type"] == "storage"
    assert span["subtype"] == "azuretable"
    assert span["action"] == "Create"
