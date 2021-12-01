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

import pytest  # isort:skip

import json
import os
import time

from elasticapm import capture_span
from elasticapm.conf import constants
from elasticapm.contrib.serverless.aws import capture_serverless, get_data_from_request, get_data_from_response


@pytest.fixture
def event_api():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_api_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_api2():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_api2_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_s3():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_s3_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_s3_batch():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_s3_batch_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_sqs():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_sqs_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_sns():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_sns_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def context():
    return SampleContext()


class SampleContext:
    """
    Stand-in for AWS lambda context object
    """

    def __init__(self):
        self.invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:my-function:someAlias"
        self.aws_request_id = "12345"


def test_request_data(event_api, event_api2):
    data = get_data_from_request(event_api, capture_body=True, capture_headers=True)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert data["headers"]["Host"] == "02plqthge2.execute-api.us-east-1.amazonaws.com"

    data = get_data_from_request(event_api2, capture_body=True, capture_headers=True)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert data["headers"]["host"] == "02plqthge2.execute-api.us-east-1.amazonaws.com"

    data = get_data_from_request(event_api, capture_body=False, capture_headers=False)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert "headers" not in data


def test_response_data():
    response = {"statusCode": "200", "headers": {"foo": "bar"}}
    data = get_data_from_response(response, capture_headers=True)
    assert data["status_code"] == 200
    assert data["headers"]["foo"] == "bar"

    response["statusCode"] = 400
    data = get_data_from_response(response, capture_headers=False)
    assert data["status_code"] == 400
    assert "headers" not in data

    data = get_data_from_response({}, capture_headers=False)
    assert not data

    response["statusCode"] = "2xx"
    data = get_data_from_response(response, capture_headers=True)
    assert data["status_code"] == 500


def test_capture_serverless_api_gateway(event_api, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "GET test_func"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200


def test_capture_serverless_api_gateway_v2(event_api2, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api2, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "GET test_func"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200


def test_capture_serverless_s3(event_s3, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_s3, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "ObjectCreated:Put basepitestbucket"
    assert transaction["span_count"]["started"] == 1


def test_capture_serverless_sns(event_sns, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_sns, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "RECEIVE basepiwstesttopic"
    assert transaction["span_count"]["started"] == 1


def test_capture_serverless_sqs(event_sqs, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_sqs, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "RECEIVE testqueue"
    assert transaction["span_count"]["started"] == 1


def test_capture_serverless_s3_batch(event_s3_batch, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless()
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_s3_batch, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "test_func"
    assert transaction["span_count"]["started"] == 1
