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
pytestmark = [pytest.mark.azurestorage]

from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient, __version__

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=basepitest;AccountKey=zkvHzuN7iu2RwXXKfPttS4o3JvayNRlz7Tm7+7IkwbxKzApp4jAmKeNgHILzvubvt7CUglM107eVL0zZPjEXFA==;EndpointSuffix=core.windows.net"

if not CONNECTION_STRING:
    pytestmark.append(
        pytest.mark.skip("Skipping azure storage tests, no AZURE_STORAGE_CONNECTION_STRING environment variable set")
    )


@pytest.fixture()
def container_client(blob_service_client):
    container_name = str(uuid.uuid4())
    container_client = blob_service_client.create_container(container_name)
    container_client.container_name = container_name

    yield container_client

    blob_service_client.delete_container(container_name)


@pytest.fixture()
def blob_service_client():
    blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    return blob_service_client


def test_list_blobs(instrument, elasticapm_client, container_client):
    elasticapm_client.begin_transaction("transaction.test")
    list(container_client.list_blobs())
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "AzureBlob ListBlobs {}".format(container_client.container_name)
    assert span["type"] == "storage"
    assert span["subtype"] == "azureblob"
    assert span["action"] == "ListBlobs"


def test_create_container(instrument, elasticapm_client, blob_service_client):
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


def test_upload(instrument, elasticapm_client, container_client, blob_service_client):
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
