#  BSD 3-Clause License
#
#  Copyright (c) 2023, Elasticsearch BV
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
import pytest

azure = pytest.importorskip("azure.functions")

import datetime
import os
from unittest import mock

import azure.functions as func

import elasticapm
from elasticapm.conf import constants
from elasticapm.contrib.serverless.azure import AzureFunctionsClient, ElasticAPMExtension, get_faas_data
from tests.fixtures import TempStoreClient


class AzureFunctionsTestClient(AzureFunctionsClient, TempStoreClient):
    pass


@pytest.mark.parametrize(
    "elasticapm_client", [{"client_class": AzureFunctionsTestClient}], indirect=["elasticapm_client"]
)
def test_service_info(elasticapm_client):
    with mock.patch.dict(
        os.environ,
        {
            "FUNCTIONS_EXTENSION_VERSION": "1.1",
            "FUNCTIONS_WORKER_RUNTIME": "MontyPython",
            "FUNCTIONS_WORKER_RUNTIME_VERSION": "2.2",
            "WEBSITE_INSTANCE_ID": "foo",
        },
    ):
        service_info = elasticapm_client.get_service_info()
        assert service_info["framework"]["name"] == "Azure Functions"
        assert service_info["framework"]["version"] == "1.1"
        assert service_info["runtime"]["name"] == "MontyPython"
        assert service_info["runtime"]["version"] == "2.2"
        assert service_info["node"]["configured_name"] == "foo"


@pytest.mark.parametrize(
    "elasticapm_client", [{"client_class": AzureFunctionsTestClient}], indirect=["elasticapm_client"]
)
def test_cloud_info(elasticapm_client):
    with mock.patch.dict(
        os.environ,
        {
            "REGION_NAME": "eu-liechtenstein",
            "WEBSITE_OWNER_NAME": "2491fc8e-f7c1-4020-b9c6-78509919fd16+my-resource-group-ARegionShortNamewebspace",
            "WEBSITE_SITE_NAME": "foo",
            "WEBSITE_RESOURCE_GROUP": "bar",
        },
    ):
        cloud_info = elasticapm_client.get_cloud_info()
        assert cloud_info["provider"] == "azure"
        assert cloud_info["region"] == "eu-liechtenstein"
        assert cloud_info["service"]["name"] == "functions"
        assert cloud_info["account"]["id"] == "2491fc8e-f7c1-4020-b9c6-78509919fd16"
        assert cloud_info["instance"]["name"] == "foo"
        assert cloud_info["project"]["name"] == "bar"


def test_extension_configure():
    try:
        with mock.patch.dict(os.environ, {"WEBSITE_SITE_NAME": "foo", "AZURE_FUNCTIONS_ENVIRONMENT": "prod"}):
            ElasticAPMExtension.configure(client_class=AzureFunctionsTestClient)
        client = ElasticAPMExtension.client
        assert client.config.metrics_interval == datetime.timedelta(0)
        assert client.config.breakdown_metrics is False
        assert client.config.central_config is False
        assert client.config.cloud_provider == "none"
        assert client.config.framework_name == "Azure Functions"
        assert client.config.service_name == "foo"
        assert client.config.environment == "prod"
    finally:
        if ElasticAPMExtension.client:
            ElasticAPMExtension.client.close()
            ElasticAPMExtension.client = None


def test_extension_configure_with_kwargs():
    try:
        ElasticAPMExtension.configure(
            client_class=AzureFunctionsTestClient, metrics_sets=["foo"], service_name="foo", environment="bar"
        )
        client = ElasticAPMExtension.client

        assert client.config.metrics_interval == datetime.timedelta(0)
        assert client.config.breakdown_metrics is False
        assert client.config.central_config is False
        assert client.config.cloud_provider == "none"
        assert client.config.framework_name == "Azure Functions"
        assert client.config.service_name == "foo"
        assert client.config.environment == "bar"
        assert client.config.metrics_sets == ["foo"]
    finally:
        if ElasticAPMExtension.client:
            ElasticAPMExtension.client.close()
            ElasticAPMExtension.client = None


@pytest.mark.parametrize(
    "elasticapm_client", [{"client_class": AzureFunctionsTestClient}], indirect=["elasticapm_client"]
)
def test_pre_post_invocation_app_level_request(elasticapm_client):
    try:
        ElasticAPMExtension.client = elasticapm_client
        request = func.HttpRequest(
            "get",
            "/foo/bar",
            headers={
                "Cookie": "foo=bar; baz=bazzinga",
                "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            },
            body=b"",
        )
        response = func.HttpResponse("", status_code=200, headers={}, mimetype="text/html")
        context = mock.Mock(function_name="foo_function", invocation_id="fooid")
        ElasticAPMExtension.pre_invocation_app_level(None, context, {"request": request})
        ElasticAPMExtension.post_invocation_app_level(None, context, func_ret=response)
        transaction = elasticapm_client.events[constants.TRANSACTION][0]
        assert transaction["name"] == "foo_function"
        assert transaction["type"] == "request"
        assert transaction["outcome"] == "success"
        assert transaction["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert transaction["parent_id"] == "b7ad6b7169203331"
        assert transaction["context"]["request"]["method"] == "GET"
        assert transaction["context"]["request"]["cookies"] == {
            "foo": "bar",
            "baz": "bazzinga",
        }
        assert transaction["context"]["request"]["url"]["full"] == "/foo/bar"
        assert transaction["context"]["response"]["status_code"] == 200

    finally:
        ElasticAPMExtension.client = None


def test_get_faas_data():
    context = mock.Mock(invocation_id="fooid", function_name="fname")
    with mock.patch.dict(
        os.environ,
        {
            "WEBSITE_OWNER_NAME": "2491fc8e-f7c1-4020-b9c6-78509919fd16+my-resource-group-ARegionShortNamewebspace",
            "WEBSITE_SITE_NAME": "foo",
            "WEBSITE_RESOURCE_GROUP": "bar",
        },
    ):
        data = get_faas_data(context, True, "request")
    assert data["coldstart"] is True
    assert data["execution"] == "fooid"
    assert data["trigger"]["type"] == "request"
    assert (
        data["id"]
        == "/subscriptions/2491fc8e-f7c1-4020-b9c6-78509919fd16/resourceGroups/bar/providers/Microsoft.Web/sites/foo/functions/fname"
    )
