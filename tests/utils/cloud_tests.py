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

import mock
import urllib3

import elasticapm.utils.cloud

GCP_DATA = b"""{
    "instance": {
        "id": 4306570268266786072,
        "machineType": "projects/513326162531/machineTypes/n1-standard-1",
        "name": "basepi-test",
        "zone": "projects/513326162531/zones/us-west3-a"
    },
    "project": {"numericProjectId": 513326162531, "projectId": "elastic-apm"}
}"""

AZURE_DATA = b"""{
    "location": "westus2",
    "name": "basepi-test",
    "resourceGroupName": "basepi-testing",
    "subscriptionId": "7657426d-c4c3-44ac-88a2-3b2cd59e6dba",
    "vmId": "e11ebedc-019d-427f-84dd-56cd4388d3a8",
    "vmScaleSetName": "",
    "vmSize": "Standard_D2s_v3",
    "zone": ""
}"""

AWS_DATA = b"""{
    "accountId": "946960629917",
    "architecture": "x86_64",
    "availabilityZone": "us-east-2a",
    "billingProducts": null,
    "devpayProductCodes": null,
    "marketplaceProductCodes": null,
    "imageId": "ami-07c1207a9d40bc3bd",
    "instanceId": "i-0ae894a7c1c4f2a75",
    "instanceType": "t2.medium",
    "kernelId": null,
    "pendingTime": "2020-06-12T17:46:09Z",
    "privateIp": "172.31.0.212",
    "ramdiskId": null,
    "region": "us-east-2",
    "version": "2017-09-30"
}"""


@mock.patch("socket.create_connection")
def test_aws_metadata(mock_socket, monkeypatch):
    class MockPoolManager:
        def request(self, *args, **kwargs):
            self.data = AWS_DATA
            return self

    monkeypatch.setattr(urllib3, "PoolManager", MockPoolManager)

    metadata = elasticapm.utils.cloud.aws_metadata()
    assert metadata == {
        "account": {"id": "946960629917"},
        "instance": {"id": "i-0ae894a7c1c4f2a75"},
        "availability_zone": "us-east-2a",
        "machine": {"type": "t2.medium"},
        "provider": "aws",
        "region": "us-east-2",
    }


@mock.patch("socket.getaddrinfo")
def test_gcp_metadata(mock_socket, monkeypatch):
    class MockPoolManager:
        def request(self, *args, **kwargs):
            self.data = GCP_DATA
            return self

    monkeypatch.setattr(urllib3, "PoolManager", MockPoolManager)

    metadata = elasticapm.utils.cloud.gcp_metadata()
    assert metadata == {
        "provider": "gcp",
        "instance": {"id": "4306570268266786072", "name": "basepi-test"},
        "project": {"id": "513326162531", "name": "elastic-apm"},
        "availability_zone": "us-west3-a",
        "region": "us-west3",
        "machine": {"type": "projects/513326162531/machineTypes/n1-standard-1"},
    }


@mock.patch("socket.create_connection")
def test_azure_metadata(mock_socket, monkeypatch):
    class MockPoolManager:
        def request(self, *args, **kwargs):
            self.data = AZURE_DATA
            return self

    monkeypatch.setattr(urllib3, "PoolManager", MockPoolManager)

    metadata = elasticapm.utils.cloud.azure_metadata()
    assert metadata == {
        "account": {"id": "7657426d-c4c3-44ac-88a2-3b2cd59e6dba"},
        "instance": {"id": "e11ebedc-019d-427f-84dd-56cd4388d3a8", "name": "basepi-test"},
        "project": {"name": "basepi-testing"},
        "machine": {"type": "Standard_D2s_v3"},
        "provider": "azure",
        "region": "westus2",
    }
