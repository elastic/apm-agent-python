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
import warnings
from typing import Optional, TypeVar
from urllib.parse import urlencode

import elasticapm
from elasticapm.base import Client, get_client
from elasticapm.conf import constants
from elasticapm.utils import encoding, get_name_from_func, nested_key
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

SERVERLESS_HTTP_REQUEST = ("api", "elb")

logger = get_logger("elasticapm.serverless")

COLD_START = True
INSTRUMENTED = False

_AWSLambdaContextT = TypeVar("_AWSLambdaContextT")


def capture_serverless(func: Optional[callable] = None, **kwargs) -> callable:
    """
    Decorator for instrumenting AWS Lambda functions.

    Example usage:

        from elasticapm import capture_serverless

        @capture_serverless
        def handler(event, context):
            return {"statusCode": r.status_code, "body": "Success!"}
    """
    if not func:
        # This allows for `@capture_serverless()` in addition to
        # `@capture_serverless` decorator usage
        return functools.partial(capture_serverless, **kwargs)

    if kwargs:
        warnings.warn(
            PendingDeprecationWarning(
                "Passing keyword arguments to capture_serverless will be deprecated in the next major release."
            )
        )

    name = kwargs.pop("name", None)

    # Disable all background threads except for transport
    kwargs["metrics_interval"] = "0ms"
    kwargs["breakdown_metrics"] = False
    if "metrics_sets" not in kwargs and "ELASTIC_APM_METRICS_SETS" not in os.environ:
        # Allow users to override metrics sets
        kwargs["metrics_sets"] = []
    kwargs["central_config"] = False
    kwargs["cloud_provider"] = "none"
    kwargs["framework_name"] = "AWS Lambda"
    if "service_name" not in kwargs and "ELASTIC_APM_SERVICE_NAME" not in os.environ:
        kwargs["service_name"] = os.environ["AWS_LAMBDA_FUNCTION_NAME"]
    if "service_version" not in kwargs and "ELASTIC_APM_SERVICE_VERSION" not in os.environ:
        kwargs["service_version"] = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")

    global INSTRUMENTED
    client = get_client()
    if not client:
        client = Client(**kwargs)
    if not client.config.debug and client.config.instrument and client.config.enabled and not INSTRUMENTED:
        elasticapm.instrument()
        INSTRUMENTED = True

    @functools.wraps(func)
    def decorated(*args, **kwds):
        if len(args) == 2:
            # Saving these for request context later
            event, context = args
        else:
            event, context = {}, {}

        if not client.config.debug and client.config.instrument and client.config.enabled:
            with _lambda_transaction(func, name, client, event, context) as sls:
                sls.response = func(*args, **kwds)
                return sls.response
        else:
            return func(*args, **kwds)

    return decorated


class _lambda_transaction(object):
    """
    Context manager for creating transactions around AWS Lambda functions.

    Begins and ends a single transaction, waiting for the transport to flush
    before releasing the context.
    """

    def __init__(
        self, func: callable, name: Optional[str], client: Client, event: dict, context: _AWSLambdaContextT
    ) -> None:
        self.func = func
        self.name = name or get_name_from_func(func)
        self.event = event
        self.context = context
        self.response = None
        self.client = client

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

        self.httpmethod = (
            nested_key(self.event, "requestContext", "httpMethod")
            or nested_key(self.event, "requestContext", "http", "method")
            or nested_key(self.event, "httpMethod")
        )

        if self.httpmethod:  # http request
            if nested_key(self.event, "requestContext", "elb"):
                self.source = "elb"
                resource = "unknown route"
            elif nested_key(self.event, "requestContext", "httpMethod"):
                self.source = "api"
                # API v1
                resource = "/{}{}".format(
                    nested_key(self.event, "requestContext", "stage"),
                    nested_key(self.event, "requestContext", "resourcePath"),
                )
            else:
                self.source = "api"
                # API v2
                route_key = nested_key(self.event, "requestContext", "routeKey")
                route_key = f"/{route_key}" if route_key.startswith("$") else route_key.split(" ", 1)[-1]
                resource = "/{}{}".format(
                    nested_key(self.event, "requestContext", "stage"),
                    route_key,
                )
            transaction_name = "{} {}".format(self.httpmethod, resource)
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

        if "Records" in self.event:
            links = [
                TraceParent.from_string(record["messageAttributes"]["traceparent"]["stringValue"])
                for record in self.event["Records"][:1000]
                if "messageAttributes" in record and "traceparent" in record["messageAttributes"]
            ]
        else:
            links = []

        self.client.begin_transaction(transaction_type, trace_parent=trace_parent, links=links)
        elasticapm.set_transaction_name(transaction_name, override=False)
        if self.source in SERVERLESS_HTTP_REQUEST:
            elasticapm.set_context(
                lambda: get_data_from_request(
                    self.event,
                    capture_body=self.client.config.capture_body in ("transactions", "all"),
                    capture_headers=self.client.config.capture_headers,
                ),
                "request",
            )
        self.set_metadata_and_context(cold_start)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Transaction teardown
        """
        if self.response and isinstance(self.response, dict):
            elasticapm.set_context(
                lambda: get_data_from_response(self.response, capture_headers=self.client.config.capture_headers),
                "response",
            )
            if "statusCode" in self.response:
                try:
                    result = "HTTP {}xx".format(int(self.response["statusCode"]) // 100)
                    elasticapm.set_transaction_result(result, override=False)
                    if result == "HTTP 5xx":
                        elasticapm.set_transaction_outcome(outcome="failure", override=False)
                except ValueError:
                    logger.warning("Lambda function's statusCode was not formed as an int. Assuming 5xx result.")
                    elasticapm.set_transaction_result("HTTP 5xx", override=False)
                    elasticapm.set_transaction_outcome(outcome="failure", override=False)
        if exc_val:
            self.client.capture_exception(exc_info=(exc_type, exc_val, exc_tb), handled=False)
            if self.source in SERVERLESS_HTTP_REQUEST:
                elasticapm.set_transaction_result("HTTP 5xx", override=False)
                elasticapm.set_transaction_outcome(http_status_code=500, override=False)
                elasticapm.set_context({"status_code": 500}, "response")
            else:
                elasticapm.set_transaction_result("failure", override=False)
                elasticapm.set_transaction_outcome(outcome="failure", override=False)

        self.client.end_transaction()
        # Collect any custom+prometheus metrics if enabled
        self.client.metrics.collect()

        try:
            logger.debug("flushing elasticapm")
            self.client._transport.flush()
            logger.debug("done flushing elasticapm")
        except ValueError:
            logger.warning("flush timed out")

    def set_metadata_and_context(self, coldstart: bool) -> None:
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
        arn = self.context.invoked_function_arn
        if len(arn.split(":")) > 7:
            arn = ":".join(arn.split(":")[:7])
        faas["id"] = arn
        faas["name"] = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        faas["version"] = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")

        if self.source == "api":
            faas["trigger"]["type"] = "http"
            faas["trigger"]["request_id"] = self.event["requestContext"]["requestId"]
            service_context["origin"] = {"name": self.event["requestContext"]["domainName"]}
            service_context["origin"]["id"] = self.event["requestContext"]["apiId"]
            service_context["origin"]["version"] = self.event.get("version", "1.0")
            cloud_context["origin"] = {}
            cloud_context["origin"]["service"] = {"name": "api gateway"}
            if ".lambda-url." in self.event["requestContext"]["domainName"]:
                cloud_context["origin"]["service"]["name"] = "lambda url"
            cloud_context["origin"]["account"] = {"id": self.event["requestContext"]["accountId"]}
            cloud_context["origin"]["provider"] = "aws"
        elif self.source == "elb":
            elb_target_group_arn = self.event["requestContext"]["elb"]["targetGroupArn"]
            faas["trigger"]["type"] = "http"
            service_context["origin"] = {"name": elb_target_group_arn.split(":")[5].split("/")[1]}
            service_context["origin"]["id"] = elb_target_group_arn
            cloud_context["origin"] = {}
            cloud_context["origin"]["service"] = {"name": "elb"}
            cloud_context["origin"]["account"] = {"id": elb_target_group_arn.split(":")[4]}
            cloud_context["origin"]["region"] = elb_target_group_arn.split(":")[3]
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
            message_context["queue"] = {"name": service_context["origin"]["name"]}
            if "SentTimestamp" in record["attributes"]:
                message_context["age"] = {"ms": int((time.time() * 1000) - int(record["attributes"]["SentTimestamp"]))}
            if self.client.config.capture_body in ("transactions", "all") and "body" in record:
                message_context["body"] = record["body"]
            if self.client.config.capture_headers and record.get("messageAttributes"):
                headers = {}
                for k, v in record["messageAttributes"].items():
                    if v and v.get("stringValue"):
                        headers[k] = v.get("stringValue")
                if headers:
                    message_context["headers"] = headers
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
            cloud_context["origin"]["account"] = {"id": record["Sns"]["TopicArn"].split(":")[4]}
            cloud_context["origin"]["provider"] = "aws"
            message_context["queue"] = {"name": service_context["origin"]["name"]}
            if "Timestamp" in record["Sns"]:
                message_context["age"] = {
                    "ms": int(
                        (
                            datetime.datetime.now()
                            - datetime.datetime.strptime(record["Sns"]["Timestamp"], r"%Y-%m-%dT%H:%M:%S.%fZ")
                        ).total_seconds()
                        * 1000
                    )
                }
            if self.client.config.capture_body in ("transactions", "all") and "Message" in record["Sns"]:
                message_context["body"] = record["Sns"]["Message"]
            if self.client.config.capture_headers and record["Sns"].get("MessageAttributes"):
                headers = {}
                for k, v in record["Sns"]["MessageAttributes"].items():
                    if v and v.get("Type") == "String":
                        headers[k] = v.get("Value")
                if headers:
                    message_context["headers"] = headers
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

        metadata["service"] = {}
        metadata["service"]["name"] = self.client.config.service_name
        metadata["service"]["framework"] = {"name": "AWS Lambda"}
        metadata["service"]["runtime"] = {
            "name": os.environ.get("AWS_EXECUTION_ENV"),
            "version": platform.python_version(),
        }
        metadata["service"]["version"] = self.client.config.service_version
        metadata["service"]["node"] = {"configured_name": os.environ.get("AWS_LAMBDA_LOG_STREAM_NAME")}
        # This is the one piece of metadata that requires deep merging. We add it manually
        # here to avoid having to deep merge in _transport.add_metadata()
        if self.client._transport._metadata:
            node_name = nested_key(self.client._transport._metadata, "service", "node", "name")
            if node_name:
                metadata["service"]["node"]["name"] = node_name

        metadata["cloud"] = {}
        metadata["cloud"]["provider"] = "aws"
        metadata["cloud"]["region"] = os.environ.get("AWS_REGION")
        metadata["cloud"]["service"] = {"name": "lambda"}
        metadata["cloud"]["account"] = {"id": arn.split(":")[4]}

        elasticapm.set_context(cloud_context, "cloud")
        elasticapm.set_context(service_context, "service")
        # faas doesn't actually belong in context, but we handle this in to_dict
        elasticapm.set_context(faas, "faas")
        if message_context:
            elasticapm.set_context(message_context, "message")
        self.client._transport.add_metadata(metadata)


def get_data_from_request(event: dict, capture_body: bool = False, capture_headers: bool = True) -> dict:
    """
    Capture context data from API gateway event
    """
    result = {}
    if capture_headers and "headers" in event:
        result["headers"] = event["headers"]

    method = (
        nested_key(event, "requestContext", "httpMethod")
        or nested_key(event, "requestContext", "http", "method")
        or nested_key(event, "httpMethod")
    )

    if not method:
        # Not API Gateway
        return result

    result["method"] = method
    if method in constants.HTTP_WITH_BODY and "body" in event:
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


def get_data_from_response(response: dict, capture_headers: bool = True) -> dict:
    """
    Capture response data from lambda return
    """
    result = {}

    if "statusCode" in response:
        try:
            result["status_code"] = int(response["statusCode"])
        except ValueError:
            # statusCode wasn't formed as an int
            # we don't log here, as we will have already logged at transaction.result handling
            result["status_code"] = 500

    if capture_headers and "headers" in response:
        result["headers"] = response["headers"]
    return result


def get_url_dict(event: dict) -> dict:
    """
    Reconstruct URL from API Gateway
    """
    headers = event.get("headers", {})
    protocol = headers.get("X-Forwarded-Proto", headers.get("x-forwarded-proto", "https"))
    host = headers.get("Host", headers.get("host", ""))
    stage = nested_key(event, "requestContext", "stage") or ""
    raw_path = event.get("rawPath", "")
    if stage:
        stage = "/" + stage
        raw_path = raw_path.split(stage)[-1]

    path = event.get("path", raw_path)
    port = headers.get("X-Forwarded-Port", headers.get("x-forwarded-port"))
    query = ""
    if "rawQueryString" in event:
        query = event["rawQueryString"]
    elif event.get("queryStringParameters"):
        if stage:  # api requires parameters encoding to build correct url
            query = "?" + urlencode(event["queryStringParameters"])
        else:  # for elb we do not have the stage
            query = "?" + "&".join(["{}={}".format(k, v) for k, v in event["queryStringParameters"].items()])

    url = protocol + "://" + host + stage + path + query

    url_dict = {
        "full": encoding.keyword_field(url),
        "protocol": protocol,
        "hostname": encoding.keyword_field(host),
        "pathname": encoding.keyword_field(stage + path),
    }

    if port:
        url_dict["port"] = port
    if query:
        url_dict["search"] = encoding.keyword_field(query)
    return url_dict
