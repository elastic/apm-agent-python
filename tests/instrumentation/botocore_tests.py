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
import pytest

from elasticapm.conf import constants
from elasticapm.instrumentation.packages.botocore import BotocoreInstrumentation

boto3 = pytest.importorskip("boto3")


pytestmark = pytest.mark.boto3


@mock.patch("botocore.endpoint.Endpoint.make_request")
def test_botocore_instrumentation(mock_make_request, instrument, elasticapm_client):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_make_request.return_value = (mock_response, {})

    elasticapm_client.begin_transaction("transaction.test")
    session = boto3.Session(aws_access_key_id="foo", aws_secret_access_key="bar", region_name="us-west-2")
    ec2 = session.client("ec2")
    ec2.describe_instances()
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "ec2:DescribeInstances"
    assert span["type"] == "aws"
    assert span["subtype"] == "ec2"
    assert span["action"] == "DescribeInstances"


def test_botocore_http_instrumentation(instrument, elasticapm_client, waiting_httpserver):
    # use a real http connection to ensure that our http instrumentation doesn't break anything
    list_bucket_response_body = b"""
<?xml version="1.0" encoding="UTF-8"?>\n
<ListAllMyBucketsResult
    xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Owner>
        <ID>1111111111111111111111111111111111111111111111111111111111111111</ID>
        <DisplayName>foo</DisplayName>
    </Owner>
    <Buckets>
        <Bucket>
            <Name>mybucket</Name>
            <CreationDate>2013-11-06T03:26:06.000Z</CreationDate>
        </Bucket>
    </Buckets>
</ListAllMyBucketsResult>"""

    list_bucket_response_headers = {
        "x-amz-id-2": "x+x+x/x=",
        "x-amz-request-id": "FA07A1210D2A2380",
        "Date": "Wed, 21 Nov 2018 08:32:24 GMT",
        "Content-Type": "application/xml",
        "Server": "AmazonS3",
    }

    waiting_httpserver.headers = list_bucket_response_headers
    waiting_httpserver.content = list_bucket_response_body
    elasticapm_client.begin_transaction("transaction.test")
    session = boto3.Session(aws_access_key_id="foo", aws_secret_access_key="bar", region_name="us-west-2")
    s3 = session.client("s3", endpoint_url=waiting_httpserver.url.replace("127.0.0.1", "localhost"))
    s3.list_buckets()
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "localhost:ListBuckets"
    assert span["type"] == "aws"
    assert span["subtype"] == "localhost"
    assert span["action"] == "ListBuckets"

    assert constants.TRACEPARENT_HEADER_NAME in waiting_httpserver.requests[0].headers


def test_nonstandard_endpoint_url(instrument, elasticapm_client):
    instrument = BotocoreInstrumentation()
    elasticapm_client.begin_transaction("test")
    module, method = BotocoreInstrumentation.instrument_list[0]
    instance = mock.Mock(_endpoint=mock.Mock(host="https://example"))
    instrument.call(module, method, lambda *args, **kwargs: None, instance, ("DescribeInstances",), {})
    transaction = elasticapm_client.end_transaction("test", "test")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "example:DescribeInstances"
