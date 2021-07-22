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

from elasticapm.conf import constants
from elasticapm.contrib.serverless.aws import capture_serverless, get_data_from_request, get_data_from_response


@pytest.fixture
def event_api():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_api_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_s3():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_s3_test_data.json")
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
        self.invoked_function_arn = "arrrrrn"
        self.aws_request_id = "12345"


def test_request_data(event_api):
    data = get_data_from_request(event_api, capture_body=True, capture_headers=True)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert data["headers"]["Host"] == "02plqthge2.execute-api.us-east-1.amazonaws.com"

    data = get_data_from_request(event_api, capture_body=False, capture_headers=False)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert "headers" not in data


def test_response_data():
    response = {"statusCode": 200, "headers": {"foo": "bar"}}

    data = get_data_from_response(response, capture_headers=True)

    assert data["status_code"] == 200
    assert data["headers"]["foo"] == "bar"

    data = get_data_from_response(response, capture_headers=False)

    assert data["status_code"] == 200
    assert "headers" not in data

    data = get_data_from_response({}, capture_headers=False)

    assert not data


def test_capture_serverless(event_api, context, elasticapm_client):

    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    capture_object = capture_serverless()
    capture_object.event = event_api
    capture_object.name = "GET"

    @capture_serverless()
    def test_func(event, context):
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
