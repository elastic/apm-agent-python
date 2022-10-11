#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import functools
import urllib.parse
from typing import TYPE_CHECKING, Optional, Tuple, Union

if TYPE_CHECKING:
    from asgiref.typing import ASGIApplication, ASGIReceiveCallable, ASGISendCallable, Scope, ASGISendEvent

import elasticapm
from elasticapm import Client, get_client, instrument
from elasticapm.conf import constants
from elasticapm.contrib.asyncio.traces import set_context
from elasticapm.utils import default_ports, encoding
from elasticapm.utils.disttracing import TraceParent


def wrap_send(send, middleware):
    @functools.wraps(send)
    async def wrapped_send(message):
        if message.get("type") == "http.response.start":
            await set_context(lambda: middleware.get_data_from_response(message, constants.TRANSACTION), "response")
            result = "HTTP {}xx".format(message["status"] // 100)
            elasticapm.set_transaction_result(result, override=False)
        await send(message)

    return wrapped_send


class ASGITracingMiddleware:
    __slots__ = ("_app", "client")

    def __init__(self, app: "ASGIApplication", **options) -> None:
        self._app = app
        client = get_client()
        if not client:
            client = Client(**options)
        self.client = client
        if self.client.config.instrument and self.client.config.enabled:
            instrument()

    async def __call__(self, scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable") -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        send = wrap_send(send, self)
        wrapped_receive = receive
        url, url_dict = self.get_url(scope)
        body = None
        if not self.client.should_ignore_url(url):
            self.client.begin_transaction(
                transaction_type="request", trace_parent=TraceParent.from_headers(scope["headers"])
            )
            self.set_transaction_name(scope["method"], url)
            if scope["method"] in constants.HTTP_WITH_BODY and self.client.config.capture_body != "off":
                messages = []
                more_body = True
                while more_body:
                    message = await receive()
                    messages.append(message)
                    more_body = message.get("more_body", False)

                body_raw = b"".join([message.get("body", b"") for message in messages])
                body = str(body_raw, errors="ignore")

                # Dispatch to the ASGI callable
                async def wrapped_receive():
                    if messages:
                        return messages.pop(0)

                    # Once that's done we can just await any other messages.
                    return await receive()

            await set_context(lambda: self.get_data_from_request(scope, constants.TRANSACTION, body), "request")

        try:
            await self._app(scope, wrapped_receive, send)
            elasticapm.set_transaction_outcome(constants.OUTCOME.SUCCESS, override=False)
            return
        except Exception as exc:
            self.client.capture_exception()
            elasticapm.set_transaction_result("HTTP 5xx", override=False)
            elasticapm.set_transaction_outcome(constants.OUTCOME.FAILURE, override=True)
            elasticapm.set_context({"status_code": 500}, "response")
            raise exc from None
        finally:
            self.client.end_transaction()

    def get_headers(self, scope_or_message: Union["Scope", "ASGISendEvent"]) -> dict[str, str]:
        headers = {}
        for k, v in scope_or_message.get("headers", {}):
            key = k.decode("latin1")
            val = v.decode("latin1")
            if key in headers:
                headers[key] = f"{headers[key]}, {val}"
            else:
                headers[key] = val
        return headers

    def get_url(self, scope: "Scope", host: Optional[str] = None) -> Tuple[str, dict[str, str]]:
        url_dict = {}
        scheme = scope.get("scheme", "http")
        server = scope.get("server", None)
        path = scope.get("root_path", "") + scope.get("path", "")

        url_dict["protocol"] = scheme + ":"

        if host:
            url = f"{scheme}://{host}{path}"
            url_dict["hostname"] = host
        elif server is not None:
            host, port = server
            url_dict["hostname"] = host
            if port:
                url_dict["port"] = port
            default_port = default_ports.get(scheme, None)
            if port != default_port:
                url = f"{scheme}://{host}:{port}{path}"
            else:
                url = f"{scheme}://{host}{path}"
        else:
            url = path
        qs = scope.get("query_string")
        if qs:
            query = "?" + urllib.parse.unquote(qs.decode("latin-1"))
            url += query
            url_dict["search"] = encoding.keyword_field(query)
        url_dict["full"] = encoding.keyword_field(url)
        return url, url_dict

    def get_ip(self, scope: "Scope", headers: dict) -> Optional[str]:
        x_forwarded_for = headers.get("x-forwarded-for")
        remote_addr = headers.get("remote-addr")
        ip: Optional[str] = None
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        elif remote_addr:
            ip = remote_addr
        elif scope.get("client"):
            ip = scope.get("client")[0]
        return ip

    async def get_data_from_request(self, scope: "Scope", event_type: str, body: Optional[str]) -> dict:
        """Loads data from incoming request for APM capturing.

        Args:
            request (Request)
            config (Config)
            event_type (str)
            body (str)

        Returns:
            dict
        """
        headers = self.get_headers(scope)
        result = {
            "method": scope["method"],
            "socket": {"remote_address": self.get_ip(scope, headers)},
            "cookies": headers.pop("cookies", {}),
        }
        if self.client.config.capture_headers:
            result["headers"] = headers
        if body and self.client.config.capture_body in ("all", event_type):
            result["body"] = body
        url, url_dict = self.get_url(scope)
        result["url"] = url_dict

        return result

    async def get_data_from_response(self, message: dict, event_type: str) -> dict:
        """Loads data from response for APM capturing.

        Args:
            message (dict)
            config (Config)
            event_type (str)

        Returns:
            dict
        """
        result = {}

        if "status" in message:
            result["status_code"] = message["status"]

        if self.client.config.capture_headers and "headers" in message:
            headers = self.get_headers(message)
            if headers:
                result["headers"] = headers

        return result

    def set_transaction_name(self, method: str, url: str):
        """
        Default implementation sets transaction name to "METHOD unknown route".
        Subclasses may add framework specific naming.
        """
        elasticapm.set_transaction_name(f"{method.upper()} unknown route")
