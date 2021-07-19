#  BSD 3-Clause License
#
#  Copyright (c) 2012, the Sentry Team, see AUTHORS for more details
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


from __future__ import absolute_import

import asyncio
import functools
from typing import Dict, Optional

import starlette
from starlette.requests import Request
from starlette.routing import Match, Mount
from starlette.types import ASGIApp, Message

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.base import Client
from elasticapm.conf import constants
from elasticapm.contrib.asyncio.traces import set_context
from elasticapm.contrib.starlette.utils import get_body, get_data_from_request, get_data_from_response
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

logger = get_logger("elasticapm.errors.client")


def make_apm_client(config: Optional[Dict] = None, client_cls=Client, **defaults) -> Client:
    """Builds ElasticAPM client.

    Args:
        config (dict): Dictionary of Client configuration. All keys must be uppercase. See `elasticapm.conf.Config`.
        client_cls (Client): Must be Client or its child.
        **defaults: Additional parameters for Client. See `elasticapm.base.Client`

    Returns:
        Client
    """
    if "framework_name" not in defaults:
        defaults["framework_name"] = "starlette"
        defaults["framework_version"] = starlette.__version__

    return client_cls(config, **defaults)


class ElasticAPM:
    """
    Starlette / FastAPI middleware for Elastic APM capturing.

    >>> apm = make_apm_client({
        >>> 'SERVICE_NAME': 'myapp',
        >>> 'DEBUG': True,
        >>> 'SERVER_URL': 'http://localhost:8200',
        >>> 'CAPTURE_HEADERS': True,
        >>> 'CAPTURE_BODY': 'all'
    >>> })

    >>> app.add_middleware(ElasticAPM, client=apm)

    Pass an arbitrary APP_NAME and SECRET_TOKEN::

    >>> elasticapm = ElasticAPM(app, service_name='myapp', secret_token='asdasdasd')

    Pass an explicit client (don't pass in additional options in this case)::

    >>> elasticapm = ElasticAPM(app, client=client)

    Capture an exception::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     elasticapm.capture_exception()

    Capture a message::

    >>> elasticapm.capture_message('hello, world!')
    """

    def __init__(self, app: ASGIApp, client: Optional[Client], **kwargs):
        """

        Args:
            app (ASGIApp): Starlette app
            client (Client): ElasticAPM Client
        """
        if client:
            self.client = client
        else:
            self.client = make_apm_client(**kwargs)

        if self.client.config.instrument and self.client.config.enabled:
            elasticapm.instrumentation.control.instrument()

        # If we ever make this a general-use ASGI middleware we should use
        # `asgiref.conpatibility.guarantee_single_callable(app)` here
        self.app = app

    async def __call__(self, scope, receive, send):
        """
        Args:
            scope: ASGI scope dictionary
            receive: receive awaitable callable
            send: send awaitable callable
        """
        # we only handle the http scope, skip anything else.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        @functools.wraps(send)
        async def wrapped_send(message):
            if message.get("type") == "http.response.start":
                await set_context(
                    lambda: get_data_from_response(message, self.client.config, constants.TRANSACTION), "response"
                )
                result = "HTTP {}xx".format(message["status"] // 100)
                elasticapm.set_transaction_result(result, override=False)
            await send(message)

        # When we consume the body from receive, we replace the streaming
        # mechanism with a mocked version -- this workaround came from
        # https://github.com/encode/starlette/issues/495#issuecomment-513138055
        body = b""
        while True:
            message = await receive()
            if not message:
                break
            if message["type"] == "http.request":
                b = message.get("body", b"")
                if b:
                    body += b
                if not message.get("more_body", False):
                    break
            if message["type"] == "http.disconnect":
                break

        async def _receive() -> Message:
            await asyncio.sleep(0)
            return {"type": "http.request", "body": body}

        request = Request(scope, receive=_receive)
        await self._request_started(request)

        try:
            await self.app(scope, _receive, wrapped_send)
            elasticapm.set_transaction_outcome(constants.OUTCOME.SUCCESS, override=False)
        except Exception:
            await self.capture_exception(
                context={"request": await get_data_from_request(request, self.client.config, constants.ERROR)}
            )
            elasticapm.set_transaction_result("HTTP 5xx", override=False)
            elasticapm.set_transaction_outcome(constants.OUTCOME.FAILURE, override=False)
            elasticapm.set_context({"status_code": 500}, "response")

            raise
        finally:
            self.client.end_transaction()

    async def capture_exception(self, *args, **kwargs):
        """Captures your exception.

        Args:
            *args:
            **kwargs:
        """
        self.client.capture_exception(*args, **kwargs)

    async def capture_message(self, *args, **kwargs):
        """Captures your message.

        Args:
            *args: Whatever
            **kwargs: Whatever
        """
        self.client.capture_message(*args, **kwargs)

    async def _request_started(self, request: Request):
        """Captures the begin of the request processing to APM.

        Args:
            request (Request)
        """
        # When we consume the body, we replace the streaming mechanism with
        # a mocked version -- this workaround came from
        # https://github.com/encode/starlette/issues/495#issuecomment-513138055
        # and we call the workaround here to make sure that regardless of
        # `capture_body` settings, we will have access to the body if we need it.
        if self.client.config.capture_body != "off":
            await get_body(request)

        if not self.client.should_ignore_url(request.url.path):
            trace_parent = TraceParent.from_headers(dict(request.headers))
            self.client.begin_transaction("request", trace_parent=trace_parent)

            await set_context(
                lambda: get_data_from_request(request, self.client.config, constants.TRANSACTION), "request"
            )
            transaction_name = self.get_route_name(request) or request.url.path
            elasticapm.set_transaction_name("{} {}".format(request.method, transaction_name), override=False)

    def get_route_name(self, request: Request) -> str:
        app = request.app
        scope = request.scope
        routes = app.routes
        route_name = self._get_route_name(scope, routes)

        # Starlette magically redirects requests if the path matches a route name with a trailing slash
        # appended or removed. To not spam the transaction names list, we do the same here and put these
        # redirects all in the same "redirect trailing slashes" transaction name
        if not route_name and app.router.redirect_slashes and scope["path"] != "/":
            redirect_scope = dict(scope)
            if scope["path"].endswith("/"):
                redirect_scope["path"] = scope["path"][:-1]
                trim = True
            else:
                redirect_scope["path"] = scope["path"] + "/"
                trim = False

            route_name = self._get_route_name(redirect_scope, routes)
            if route_name is not None:
                route_name = route_name + "/" if trim else route_name[:-1]
        return route_name

    def _get_route_name(self, scope, routes, route_name=None):
        for route in routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                route_name = route.path
                child_scope = {**scope, **child_scope}
                if isinstance(route, Mount) and route.routes:
                    child_route_name = self._get_route_name(child_scope, route.routes, route_name)
                    if child_route_name is None:
                        route_name = None
                    else:
                        route_name += child_route_name
                return route_name
            elif match == Match.PARTIAL and route_name is None:
                route_name = route.path
