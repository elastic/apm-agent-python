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
from elasticapm.contrib.serverless.aws import (
    capture_serverless,
    get_data_from_request,
    get_data_from_response,
    should_normalize_headers,
)


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
def event_lurl():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_lurl_test_data.json")
    with open(aws_data_file) as f:
        return json.load(f)


@pytest.fixture
def event_elb():
    aws_data_file = os.path.join(os.path.dirname(__file__), "aws_elb_test_data.json")
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
def event_list():
    """
    Lambda functions can receive the raw output of Step Functions as the event.
    Because it's any valid JSON, it can be a list as well, with no useful
    context information.
    """
    return ["foo", "bar", "baz"]


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
    assert (
        data["url"]["full"]
        == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all?test%40key=test%40value"
    )
    assert data["headers"]["Host"] == "02plqthge2.execute-api.us-east-1.amazonaws.com"

    data = get_data_from_request(event_api2, capture_body=True, capture_headers=True)

    assert data["method"] == "GET"
    assert data["url"]["full"] == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all"
    assert data["headers"]["host"] == "02plqthge2.execute-api.us-east-1.amazonaws.com"

    data = get_data_from_request(event_api, capture_body=False, capture_headers=False)

    assert data["method"] == "GET"
    assert (
        data["url"]["full"]
        == "https://02plqthge2.execute-api.us-east-1.amazonaws.com/dev/fetch_all?test%40key=test%40value"
    )
    assert "headers" not in data


def test_elb_request_data(event_elb):
    data = get_data_from_request(event_elb, capture_body=True, capture_headers=True)

    assert data["method"] == "POST"
    assert (
        data["url"]["full"]
        == "https://blabla.com/toolz/api/v2.0/downloadPDF/PDF_2020-09-11_11-06-01.pdf?test%40key=test%40value&language=en-DE"
    )
    assert data["headers"]["host"] == "blabla.com"
    assert data["body"] == "blablablabody"

    data = get_data_from_request(event_elb, capture_body=False, capture_headers=False)

    assert data["method"] == "POST"
    assert (
        data["url"]["full"]
        == "https://blabla.com/toolz/api/v2.0/downloadPDF/PDF_2020-09-11_11-06-01.pdf?test%40key=test%40value&language=en-DE"
    )
    assert "headers" not in data
    assert data["body"] == "[REDACTED]"


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

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "GET /dev/fetch_all"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200


def test_capture_serverless_api_gateway_with_args_deprecated(event_api, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    with pytest.warns(PendingDeprecationWarning):

        @capture_serverless(name="test_func")
        def test_func(event, context):
            with capture_span("test_span"):
                time.sleep(0.01)
            return {"statusCode": 200, "headers": {"foo": "bar"}}

        test_func(event_api, context)

        assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
        transaction = elasticapm_client.events[constants.TRANSACTION][0]

        assert transaction["name"] == "GET /dev/fetch_all"
        assert transaction["result"] == "HTTP 2xx"
        assert transaction["span_count"]["started"] == 1
        assert transaction["context"]["request"]["method"] == "GET"
        assert transaction["context"]["request"]["headers"]
        assert transaction["context"]["response"]["status_code"] == 200


def test_capture_serverless_api_gateway_v2(event_api2, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api2, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "GET /dev/fetch_all"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200
    assert transaction["context"]["cloud"]["origin"]["service"]["name"] == "api gateway"


def test_capture_serverless_lambda_url(event_lurl, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_lurl, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "GET /dev/fetch_all"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "GET"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200
    assert transaction["context"]["cloud"]["origin"]["service"]["name"] == "lambda url"


def test_capture_serverless_elb(event_elb, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_elb, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "POST unknown route"
    assert transaction["result"] == "HTTP 2xx"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["request"]["method"] == "POST"
    assert transaction["context"]["request"]["headers"]
    assert transaction["context"]["response"]["status_code"] == 200
    assert transaction["context"]["service"]["origin"]["name"] == "lambda-279XGJDqGZ5rsrHC2Fjr"
    assert transaction["trace_id"] == "12345678901234567890123456789012"


def test_capture_serverless_s3(event_s3, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
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

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_sns, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "RECEIVE basepiwstesttopic"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["message"]["headers"]["Population"] == "1250800"
    assert transaction["context"]["message"]["headers"]["City"] == "Any City"


def test_capture_serverless_sqs(event_sqs, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_sqs, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "RECEIVE testqueue"
    assert transaction["span_count"]["started"] == 1
    assert transaction["context"]["message"]["headers"]["Population"] == "1250800"
    assert transaction["context"]["message"]["headers"]["City"] == "Any City"
    assert len(transaction["links"]) == 1
    assert transaction["links"][0] == {"trace_id": "0af7651916cd43dd8448eb211c80319c", "span_id": "b7ad6b7169203331"}


def test_capture_serverless_s3_batch(event_s3_batch, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return

    test_func(event_s3_batch, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "test_func"
    assert transaction["span_count"]["started"] == 1


@pytest.mark.parametrize("elasticapm_client", [{"service_name": "override"}], indirect=True)
def test_service_name_override(event_api, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api, context)

    assert elasticapm_client.build_metadata()["service"]["name"] == "override"


def test_capture_serverless_list_event(event_list, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_list, context)

    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1
    transaction = elasticapm_client.events[constants.TRANSACTION][0]

    assert transaction["name"] == "test_func"


def test_partial_transaction(event_api, context, sending_elasticapm_client):
    import elasticapm.contrib.serverless.aws

    elasticapm.contrib.serverless.aws.REGISTER_PARTIAL_TRANSACTIONS = True
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"
    os.environ["ELASTIC_APM_LAMBDA_APM_SERVER"] = "http://localhost:8200"

    @capture_serverless
    def test_func(event, context):
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api, context)

    assert len(sending_elasticapm_client.httpserver.requests) == 2

    # There should be no spans from the partial transaction
    for payload in sending_elasticapm_client.httpserver.payloads[1]:
        assert "span" not in payload

    request = sending_elasticapm_client.httpserver.requests[0]
    assert request.full_path == "/register/transaction?"
    assert request.content_type == "application/vnd.elastic.apm.transaction+ndjson"
    assert b"metadata" in request.data
    assert b"AWS Lambda" in request.data
    assert b"transaction" in request.data
    sending_elasticapm_client.close()


def test_partial_transaction_failure(event_api, context, sending_elasticapm_client):
    import elasticapm.contrib.serverless.aws

    elasticapm.contrib.serverless.aws.REGISTER_PARTIAL_TRANSACTIONS = True
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"
    os.environ["ELASTIC_APM_LAMBDA_APM_SERVER"] = "http://localhost:8200"
    sending_elasticapm_client.httpserver.code = 404
    sending_elasticapm_client.httpserver.content = "go away"

    @capture_serverless
    def test_func(event, context):
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    test_func(event_api, context)
    test_func(event_api, context)

    assert len(sending_elasticapm_client.httpserver.requests) == 3
    request = sending_elasticapm_client.httpserver.requests[0]
    assert request.full_path == "/register/transaction?"
    assert request.content_type == "application/vnd.elastic.apm.transaction+ndjson"
    assert b"metadata" in request.data
    assert b"AWS Lambda" in request.data
    assert b"transaction" in request.data
    sending_elasticapm_client.close()


def test_with_headers_as_none(event_api2, context, elasticapm_client):
    os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "test_func"

    @capture_serverless
    def test_func(event, context):
        with capture_span("test_span"):
            time.sleep(0.01)
        return {"statusCode": 200, "headers": {"foo": "bar"}}

    event_api2["headers"] = None

    test_func(event_api2, context)
    assert len(elasticapm_client.events[constants.TRANSACTION]) == 1


def test_should_normalize_headers_true(event_api, event_elb):
    assert should_normalize_headers(event_api) is True
    assert should_normalize_headers(event_elb) is True


def test_should_normalize_headers_false(event_api2, event_lurl, event_s3, event_s3_batch, event_sqs, event_sns):
    assert should_normalize_headers(event_api2) is False
    assert should_normalize_headers(event_lurl) is False
    assert should_normalize_headers(event_s3) is False
    assert should_normalize_headers(event_s3_batch) is False
    assert should_normalize_headers(event_sqs) is False
    assert should_normalize_headers(event_sns) is False
