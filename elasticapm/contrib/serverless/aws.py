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

import base64
import datetime
import functools
import json
import os
import platform
import time

import elasticapm
from elasticapm.base import Client, get_client
from elasticapm.conf import constants
from elasticapm.utils import compat, encoding, get_name_from_func
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.serverless")

COLD_START = True


class capture_serverless(object):
    """
    Context manager and decorator designed for instrumenting serverless
    functions.

    Begins and ends a single transaction, waiting for the transport to flush
    before returning from the wrapped function.

    Example usage:

        from elasticapm import capture_serverless

        @capture_serverless()
        def handler(event, context):
            return {"statusCode": r.status_code, "body": "Success!"}

    Note: This is an experimental feature, and we may introduce breaking
    changes in the future.
    """

    def __init__(self, name=None, **kwargs):
        self.name = name
        self.event = {}
        self.context = {}
        self.response = None

        # Disable all background threads except for transport
        kwargs["metrics_interval"] = "0ms"
        kwargs["central_config"] = False
        kwargs["cloud_provider"] = "none"
        kwargs["framework_name"] = "AWS Lambda"
        # TODO this can probably be removed once the extension proxies the serverinfo endpoint
        kwargs["server_version"] = (8, 0, 0)
        if "service_name" not in kwargs:
            kwargs["service_name"] = os.environ["AWS_LAMBDA_FUNCTION_NAME"]

        self.client = get_client()
        if not self.client:
            self.client = Client(**kwargs)
        if not self.client.config.debug and self.client.config.instrument and self.client.config.enabled:
            elasticapm.instrument()

    def __call__(self, func):
        self.name = self.name or get_name_from_func(func)

        @functools.wraps(func)
        def decorated(*args, **kwds):
            if len(args) == 2:
                # Saving these for request context later
                self.event, self.context = args
            else:
                self.event, self.context = {}, {}
            if not self.client.config.debug and self.client.config.instrument and self.client.config.enabled:
                with self:
                    self.response = func(*args, **kwds)
                    return self.response
            else:
                return func(*args, **kwds)

        return decorated

    def __enter__(self):
        """
        Transaction setup
        """
        trace_parent = TraceParent.from_headers(self.event.get("headers", {}))

        global COLD_START
        cold_start = COLD_START
        COLD_START = False

        self.source = "other"
        transaction_type = "request"
        transaction_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", self.name)

        if "httpMethod" in self.event:  # API Gateway
            self.source = "api"
            if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
                transaction_name = "{} {}".format(self.event["httpMethod"], os.environ["AWS_LAMBDA_FUNCTION_NAME"])
            else:
                transaction_name = self.name
        elif "Records" in self.event and len(self.event["Records"]) == 1:
            record = self.event["Records"][0]
            if record.get("eventSource") == "aws:s3":  # S3
                self.source = "s3"
                transaction_name = "{} {}".format(record["eventName"], record["s3"]["bucket"]["name"])
            elif record.get("EventSource") == "aws:sns":  # SNS
                self.source = "sns"
                transaction_type = "messaging"
                transaction_name = "RECEIVE {}".format(record["Sns"]["TopicArn"].split(":")[5])
            elif record.get("eventSource") == "aws:sqs":  # SQS
                self.source = "sqs"
                transaction_type = "messaging"
                transaction_name = "RECEIVE {}".format(record["eventSourceARN"].split(":")[5])

        self.transaction = self.client.begin_transaction(transaction_type, trace_parent=trace_parent)
        elasticapm.set_transaction_name(transaction_name, override=False)
        if self.source == "api":
            elasticapm.set_context(
                lambda: get_data_from_request(
                    self.event,
                    capture_body=self.client.config.capture_body in ("transactions", "all"),
                    capture_headers=self.client.config.capture_headers,
                ),
                "request",
            )
        self.set_metadata_and_context(cold_start)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Transaction teardown
        """
        if exc_val:
            self.client.capture_exception(exc_info=(exc_type, exc_val, exc_tb), handled=False)

        if self.response and isinstance(self.response, dict):
            elasticapm.set_context(
                lambda: get_data_from_response(self.response, capture_headers=self.client.config.capture_headers),
                "response",
            )
            status_code = None
            try:
                for k, v in self.response.items():
                    if k.lower() == "statuscode":
                        status_code = v
                        break
            except AttributeError:
                pass
            if status_code:
                result = "HTTP {}xx".format(int(status_code) // 100)
                elasticapm.set_transaction_result(result, override=False)

        self.client.end_transaction()

        try:
            logger.debug("flushing elasticapm")
            self.client._transport.flush()
            logger.debug("done flushing elasticapm")
        except ValueError:
            logger.warning("flush timed out")

    def set_metadata_and_context(self, coldstart):
        """
        Process the metadata and context fields for this request
        """
        metadata = {}
        cloud_context = {"origin": {"provider": "aws"}}
        service_context = {}
        message_context = {}

        faas = {}
        faas["coldstart"] = coldstart
        faas["trigger"] = {"type": "other"}
        faas["execution"] = self.context.aws_request_id

        if self.source == "api":
            faas["trigger"]["type"] = "http"
            faas["trigger"]["request_id"] = self.event["requestContext"]["requestId"]
            service_context["origin"] = {
                "name": "{} {}/{}".format(
                    self.event["requestContext"]["httpMethod"],
                    self.event["requestContext"]["resourcePath"],
                    self.event["requestContext"]["stage"],
                )
            }
            service_context["origin"]["id"] = self.event["requestContext"]["apiId"]
            service_context["origin"]["version"] = "2.0" if self.event["headers"]["Via"].startswith("2.0") else "1.0"
            cloud_context["origin"] = {}
            cloud_context["origin"]["service"] = {"name": "api gateway"}
            cloud_context["origin"]["account"] = {"id": self.event["requestContext"]["accountId"]}
            cloud_context["origin"]["provider"] = "aws"
        elif self.source == "sqs":
            record = self.event["Records"][0]
            faas["trigger"]["type"] = "pubsub"
            faas["trigger"]["request_id"] = record["messageId"]
            service_context["origin"] = {}
            service_context["origin"]["name"] = record["eventSourceARN"].split(":")[5]
            service_context["origin"]["id"] = record["eventSourceARN"]
            cloud_context["origin"] = {}
            cloud_context["origin"]["service"] = {"name": "sqs"}
            cloud_context["origin"]["region"] = record["awsRegion"]
            cloud_context["origin"]["account"] = {"id": record["eventSourceARN"].split(":")[4]}
            cloud_context["origin"]["provider"] = "aws"
            message_context["queue"] = record["eventSourceARN"]
            if "SentTimestamp" in record["attributes"]:
                message_context["age"] = int((time.time() * 1000) - int(record["attributes"]["SentTimestamp"]))
            if self.client.config.capture_body in ("transactions", "all") and "body" in record:
                message_context["body"] = record["body"]
            if self.client.config.capture_headers and record["messageAttributes"]:
                message_context["headers"] = record["messageAttributes"]
        elif self.source == "sns":
            record = self.event["Records"][0]
            faas["trigger"]["type"] = "pubsub"
            faas["trigger"]["request_id"] = record["Sns"]["TopicArn"]
            service_context["origin"] = {}
            service_context["origin"]["name"] = record["Sns"]["TopicArn"].split(":")[5]
            service_context["origin"]["id"] = record["Sns"]["TopicArn"]
            service_context["origin"]["version"] = record["EventVersion"]
            service_context["origin"]["service"] = {"name": "sns"}
            cloud_context["origin"] = {}
            cloud_context["origin"]["region"] = record["Sns"]["TopicArn"].split(":")[3]
            cloud_context["origin"]["account_id"] = record["Sns"]["TopicArn"].split(":")[4]
            cloud_context["origin"]["provider"] = "aws"
            message_context["queue"] = record["Sns"]["TopicArn"]
            if "Timestamp" in record["Sns"]:
                message_context["age"] = int(
                    (
                        datetime.datetime.now()
                        - datetime.datetime.strptime(record["Sns"]["Timestamp"], r"%Y-%m-%dT%H:%M:%S.%fZ")
                    ).total_seconds()
                    * 1000
                )
            if self.client.config.capture_body in ("transactions", "all") and "Message" in record["Sns"]:
                message_context["body"] = record["Sns"]["Message"]
            if self.client.config.capture_headers and record["Sns"]["MessageAttributes"]:
                message_context["headers"] = record["Sns"]["MessageAttributes"]
        elif self.source == "s3":
            record = self.event["Records"][0]
            faas["trigger"]["type"] = "datasource"
            faas["trigger"]["request_id"] = record["responseElements"]["x-amz-request-id"]
            service_context["origin"] = {}
            service_context["origin"]["name"] = record["s3"]["bucket"]["name"]
            service_context["origin"]["id"] = record["s3"]["bucket"]["arn"]
            service_context["origin"]["version"] = record["eventVersion"]
            cloud_context["origin"] = {}
            cloud_context["origin"]["service"] = {"name": "s3"}
            cloud_context["origin"]["region"] = record["awsRegion"]
            cloud_context["origin"]["provider"] = "aws"

        metadata["faas"] = faas

        metadata["service"] = {}
        metadata["service"]["name"] = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        metadata["service"]["framework"] = {"name": "AWS Lambda"}
        metadata["service"]["runtime"] = {
            "name": os.environ.get("AWS_EXECUTION_ENV"),
            "version": platform.python_version(),
        }
        arn = self.context.invoked_function_arn
        if len(arn.split(":")) > 7:
            arn = ":".join(arn.split(":")[:7])
        metadata["service"]["id"] = arn
        metadata["service"]["version"] = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")
        metadata["service"]["node"] = {"configured_name": os.environ.get("AWS_LAMBDA_LOG_STREAM_NAME")}
        # This is the one piece of metadata that requires deep merging. We add it manually
        # here to avoid having to deep merge in _transport.add_metadata()
        if self.client._transport._metadata:
            node_name = self.client._transport._metadata.get("service", {}).get("node", {}).get("name")
            if node_name:
                metadata["service"]["node"]["name"] = node_name

        metadata["cloud"] = {}
        metadata["cloud"]["provider"] = "aws"
        metadata["cloud"]["region"] = os.environ.get("AWS_REGION")
        metadata["cloud"]["service"] = {"name": "lambda"}
        metadata["cloud"]["account"] = {"id": arn.split(":")[4]}

        elasticapm.set_context(cloud_context, "cloud")
        elasticapm.set_context(service_context, "service")
        if message_context:
            elasticapm.set_context(service_context, "message")
        self.client._transport.add_metadata(metadata)


def get_data_from_request(event, capture_body=False, capture_headers=True):
    """
    Capture context data from API gateway event
    """
    result = {}
    if capture_headers and "headers" in event:
        result["headers"] = event["headers"]
    if "httpMethod" not in event:
        # Not API Gateway
        return result

    result["method"] = event["httpMethod"]
    if event["httpMethod"] in constants.HTTP_WITH_BODY and "body" in event:
        body = event["body"]
        if capture_body:
            if event.get("isBase64Encoded"):
                body = base64.b64decode(body)
            else:
                try:
                    jsonbody = json.loads(body)
                    body = jsonbody
                except Exception:
                    pass

        if body is not None:
            result["body"] = body if capture_body else "[REDACTED]"

    result["url"] = get_url_dict(event)
    return result


def get_data_from_response(response, capture_headers=True):
    """
    Capture response data from lambda return
    """
    result = {}

    if "statusCode" in response:
        result["status_code"] = response["statusCode"]

    if capture_headers and "headers" in response:
        result["headers"] = response["headers"]
    return result


def get_url_dict(event):
    """
    Reconstruct URL from API Gateway
    """
    headers = event.get("headers", {})
    proto = headers.get("X-Forwarded-Proto", "https")
    host = headers.get("Host", "")
    path = event.get("path", "")
    port = headers.get("X-Forwarded-Port")
    stage = "/" + event.get("requestContext", {}).get("stage", "")
    query = ""
    if event.get("queryStringParameters"):
        query = "?"
        for k, v in compat.iteritems(event["queryStringParameters"]):
            query += "{}={}".format(k, v)
    url = proto + "://" + host + stage + path + query

    url_dict = {
        "full": encoding.keyword_field(url),
        "protocol": proto,
        "hostname": encoding.keyword_field(host),
        "pathname": encoding.keyword_field(stage + path),
    }

    if port:
        url_dict["port"] = port
    if query:
        url_dict["search"] = encoding.keyword_field(query)
    return url_dict
