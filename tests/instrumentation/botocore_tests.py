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

import mock
import pytest

from elasticapm.conf import constants
from elasticapm.instrumentation.packages.botocore import BotocoreInstrumentation
from elasticapm.utils.compat import urlparse

boto3 = pytest.importorskip("boto3")


pytestmark = [pytest.mark.boto3]

os.environ["AWS_ACCESS_KEY_ID"] = "key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "secret"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

LOCALSTACK_ENDPOINT = os.environ.get("AWS_URL", None)

from boto3.dynamodb.types import TypeSerializer

dynamodb_serializer = TypeSerializer()

if not LOCALSTACK_ENDPOINT:
    pytestmark.append(pytest.mark.skip("Skipping botocore tests, no AWS_URL environment variable set"))

LOCALSTACK_ENDPOINT_URL = urlparse.urlparse(LOCALSTACK_ENDPOINT)


@pytest.fixture()
def dynamodb():
    db = boto3.client("dynamodb", endpoint_url="http://localhost:4566")
    db.create_table(
        TableName="Movies",
        KeySchema=[
            {"AttributeName": "year", "KeyType": "HASH"},  # Partition key
            {"AttributeName": "title", "KeyType": "RANGE"},  # Sort key
        ],
        AttributeDefinitions=[
            {"AttributeName": "year", "AttributeType": "N"},
            {"AttributeName": "title", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
    )
    yield db
    db.delete_table(TableName="Movies")


def test_botocore_instrumentation(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    ec2 = boto3.client("ec2", endpoint_url=LOCALSTACK_ENDPOINT)
    ec2.describe_instances()
    elasticapm_client.end_transaction("MyView")
    span = elasticapm_client.events[constants.SPAN][0]

    assert span["name"] == "EC2:DescribeInstances"
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


def test_s3(instrument, elasticapm_client):
    client = boto3.client("s3", endpoint_url=LOCALSTACK_ENDPOINT)
    elasticapm_client.begin_transaction("test")
    client.create_bucket(Bucket="xyz")
    client.put_object(Bucket="xyz", Key="abc", Body=b"foo")
    client.list_objects(Bucket="xyz")
    elasticapm_client.end_transaction("test", "test")
    transaction = elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    for span in spans:
        assert span["type"] == "storage"
        assert span["subtype"] == "s3"
        assert span["context"]["destination"]["address"] == LOCALSTACK_ENDPOINT_URL.hostname
        assert span["context"]["destination"]["port"] == LOCALSTACK_ENDPOINT_URL.port
        assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
        assert span["context"]["destination"]["name"] == "s3"
        assert span["context"]["destination"]["resource"] == "xyz"
        assert span["context"]["destination"]["service"]["type"] == "storage"
    assert spans[0]["name"] == "S3 CreateBucket xyz"
    assert spans[0]["action"] == "CreateBucket"
    assert spans[1]["name"] == "S3 PutObject xyz"
    assert spans[1]["action"] == "PutObject"
    assert spans[2]["name"] == "S3 ListObjects xyz"
    assert spans[2]["action"] == "ListObjects"


def test_dynamodb(instrument, elasticapm_client, dynamodb):
    elasticapm_client.begin_transaction("test")
    response = dynamodb.put_item(
        TableName="Movies",
        Item={"title": dynamodb_serializer.serialize("Independence Day"), "year": dynamodb_serializer.serialize(1994)},
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = dynamodb.get_item(
        TableName="Movies",
        Key={
            "title": {
                "S": '"Independence Day"',
            },
            "year": {
                "N": "1994",
            },
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = dynamodb.delete_item(
        TableName="Movies",
        Key={
            "title": {
                "S": '"Independence Day"',
            },
            "year": {
                "N": "1994",
            },
        },
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    for span in spans:
        assert span["type"] == "db"
        assert span["subtype"] == "dynamodb"
        assert span["action"] == "query"
        assert span["context"]["destination"]["address"] == LOCALSTACK_ENDPOINT_URL.hostname
        assert span["context"]["destination"]["port"] == LOCALSTACK_ENDPOINT_URL.port
        assert span["context"]["destination"]["cloud"]["region"] == "us-east-1"
        assert span["context"]["destination"]["name"] == "dynamodb"
        # assert span["context"]["destination"]["resource"] == "xyz"
        # assert span["context"]["destination"]["service"]["type"] == "storage"
    assert span[0]["name"] == "DynamoDB PutItem Movies"
    assert span[1]["name"] == "DynamoDB GetItem Movies"
    assert span[2]["name"] == "DynamoDB DeleteItem Movies"


def test_sns(instrument, elasticapm_client):
    sns = boto3.client("sns", endpoint_url=LOCALSTACK_ENDPOINT)
    elasticapm_client.begin_transaction("test")
    response = sns.create_topic(Name="mytopic")
    topic_arn = response["TopicArn"]
    response = sns.list_topics()
    sns.publish(TopicArn=topic_arn, Subject="Saying", Message="this is my message to you-ou-ou")
    elasticapm_client.end_transaction("test", "test")
    spans = elasticapm_client.events[constants.SPAN]
    assert spans[2]["name"] == "SNS Publish mytopic"
    assert spans[2]["type"] == "messaging"
    assert spans[2]["subtype"] == "sns"
    assert spans[2]["action"] == "send"
