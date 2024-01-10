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

import os
import threading
from http.cookies import SimpleCookie
from typing import Dict, Optional, TypeVar

import azure.functions as func
from azure.functions.extension import AppExtensionBase

import elasticapm
from elasticapm.base import Client
from elasticapm.conf import constants
from elasticapm.utils import get_url_dict
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

SERVERLESS_HTTP_REQUEST = ("api", "elb")

logger = get_logger("elasticapm.serverless")

_AnnotatedFunctionT = TypeVar("_AnnotatedFunctionT")

_cold_start_lock = threading.Lock()
COLD_START = True


class AzureFunctionsClient(Client):
    def get_service_info(self):
        service_info = super().get_service_info()
        service_info["framework"] = {
            "name": "Azure Functions",
            "version": os.environ.get("FUNCTIONS_EXTENSION_VERSION"),
        }
        service_info["runtime"] = {
            "name": os.environ.get("FUNCTIONS_WORKER_RUNTIME"),
            "version": os.environ.get("FUNCTIONS_WORKER_RUNTIME_VERSION"),
        }
        service_info["node"] = {"configured_name": os.environ.get("WEBSITE_INSTANCE_ID")}
        return service_info

    def get_cloud_info(self):
        cloud_info = super().get_cloud_info()
        cloud_info.update(
            {"provider": "azure", "region": os.environ.get("REGION_NAME"), "service": {"name": "functions"}}
        )
        account_id = get_account_id()
        if account_id:
            cloud_info["account"] = {"id": account_id}
        if "WEBSITE_SITE_NAME" in os.environ:
            cloud_info["instance"] = {"name": os.environ["WEBSITE_SITE_NAME"]}
        if "WEBSITE_RESOURCE_GROUP" in os.environ:
            cloud_info["project"] = {"name": os.environ["WEBSITE_RESOURCE_GROUP"]}
        return cloud_info


class ElasticAPMExtension(AppExtensionBase):
    client = None

    @classmethod
    def init(cls) -> None:
        """The function will be executed when the extension is loaded.
        Happens when Azure Functions customers import the extension module.
        """
        elasticapm.instrument()

    @classmethod
    def configure(cls, client_class=AzureFunctionsClient, **kwargs) -> None:
        client = elasticapm.get_client()
        if not client:
            kwargs["metrics_interval"] = "0ms"
            kwargs["breakdown_metrics"] = "false"
            if "metric_sets" not in kwargs and "ELASTIC_APM_METRICS_SETS" not in os.environ:
                # Allow users to override metrics sets
                kwargs["metrics_sets"] = []
            kwargs["central_config"] = "false"
            kwargs["cloud_provider"] = "none"
            kwargs["framework_name"] = "Azure Functions"
            if (
                "service_name" not in kwargs
                and "ELASTIC_APM_SERVICE_NAME" not in os.environ
                and "WEBSITE_SITE_NAME" in os.environ
            ):
                kwargs["service_name"] = os.environ["WEBSITE_SITE_NAME"]
            if (
                "environment" not in kwargs
                and "ELASTIC_APM_ENVIRONMENT" not in os.environ
                and "AZURE_FUNCTIONS_ENVIRONMENT" in os.environ
            ):
                kwargs["environment"] = os.environ["AZURE_FUNCTIONS_ENVIRONMENT"]
            client = AzureFunctionsClient(**kwargs)
        cls.client = client

    @classmethod
    def pre_invocation_app_level(cls, logger, context, func_args: Dict[str, object] = None, *args, **kwargs) -> None:
        """
        This must be implemented as a @staticmethod. It will be called right
        before a customer's function is being executed.
        """
        client = cls.client
        if not client:
            return
        global COLD_START
        with _cold_start_lock:
            cold_start, COLD_START = COLD_START, False
        tp: Optional[TraceParent] = None
        transaction_type = "request"
        http_request_data = None
        trigger_type = None
        if func_args:
            for arg in func_args.values():
                if isinstance(arg, func.HttpRequest):
                    tp = TraceParent.from_headers(arg.headers) if arg.headers else None
                    transaction_type = "request"
                    http_request_data = lambda: get_data_from_request(
                        arg, client.config.capture_headers, client.config.capture_body in ("transactions", "all")
                    )
                    trigger_type = "request"
                    break
                if isinstance(arg, func.TimerRequest):
                    transaction_type = "timer"
                    trigger_type = "timer"
                    break

        cls.client.begin_transaction(transaction_type, trace_parent=tp)
        if http_request_data:
            elasticapm.set_context(http_request_data, "request")
        elasticapm.set_context(lambda: get_faas_data(context, cold_start, trigger_type), "faas")

    @classmethod
    def post_invocation_app_level(
        cls, logger, context, func_args: Dict[str, object] = None, func_ret=Optional[object], *args, **kwargs
    ) -> None:
        client = cls.client
        if isinstance(func_ret, func.HttpResponse):
            elasticapm.set_context(lambda: get_data_from_response(func_ret, client.config.capture_headers), "response")
            elasticapm.set_transaction_outcome(http_status_code=func_ret.status_code)
            elasticapm.set_transaction_result(f"HTTP {func_ret.status_code // 100}xx")
        client.end_transaction(context.function_name)


def get_data_from_request(request: func.HttpRequest, capture_headers=False, capture_body=False):
    result = {
        "method": request.method,
    }
    if "Cookie" in request.headers:
        cookie = SimpleCookie()
        cookie.load(request.headers["Cookie"])
        result["cookies"] = {k: v.value for k, v in cookie.items()}
    if capture_headers and request.headers:
        result["headers"] = dict(request.headers)
    if capture_body and request.method in constants.HTTP_WITH_BODY:
        result["body"] = request.get_body()
    result["url"] = get_url_dict(request.url)
    return result


def get_data_from_response(response: func.HttpResponse, capture_headers: bool = False):
    result = {
        "status_code": response.status_code,
    }
    if capture_headers:
        result["headers"] = dict(response.headers)
    return result


def get_faas_data(context: func.Context, cold_start: bool, trigger_type: Optional[str]) -> dict:
    account_id = get_account_id()
    resource_group = os.environ.get("WEBSITE_RESOURCE_GROUP", None)
    app_name = os.environ.get("WEBSITE_SITE_NAME", None)
    function_name = context.function_name
    data = {
        "coldstart": cold_start,
        "execution": context.invocation_id,
    }
    if trigger_type:
        data["trigger"] = {"type": trigger_type}
    if account_id and resource_group and app_name and function_name:
        data["id"] = (
            f"/subscriptions/{account_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/sites/{app_name}/"
            + f"functions/{function_name}"
        )
    if app_name and function_name:
        data["name"] = f"{app_name}/{function_name}"
    return data


def get_account_id() -> Optional[str]:
    return os.environ["WEBSITE_OWNER_NAME"].split("+", 1)[0] if "WEBSITE_OWNER_NAME" in os.environ else None
