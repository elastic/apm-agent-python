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

import starlette
from starlette.types import ASGIApp
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.base import Client
from elasticapm.contrib.starlette.utils import get_data_from_request, get_data_from_response
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger
from elasticapm.contrib.asyncio.traces import set_context


logger = get_logger("elasticapm.errors.client")


def make_apm_client(config: dict, client_cls=Client, **defaults) -> Client:
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


class ElasticAPM(BaseHTTPMiddleware):
    """
    Starlette / FastAPI middleware for Elastic APM capturing.

    >>> elasticapm = make_apm_client({
        >>> 'SERVICE_NAME': 'myapp',
        >>> 'DEBUG': True,
        >>> 'SERVER_URL': 'http://localhost:8200',
        >>> 'CAPTURE_HEADERS': True,
        >>> 'CAPTURE_BODY': 'all'
    >>> })

    >>> app.add_middleware(ElasticAPM, client=elasticapm)

    Pass an arbitrary APP_NAME and SECRET_TOKEN::

    >>> elasticapm = ElasticAPM(app, service_name='myapp', secret_token='asdasdasd')

    Pass an explicit client::

    >>> elasticapm = ElasticAPM(app, client=client)

    Automatically configure logging::

    >>> elasticapm = ElasticAPM(app, logging=True)

    Capture an exception::

    >>> try:
    >>>     1 / 0
    >>> except ZeroDivisionError:
    >>>     elasticapm.capture_exception()

    Capture a message::

    >>> elasticapm.capture_message('hello, world!')
    """

    def __init__(self, app: ASGIApp, client: Client):
        """

        Args:
            app (ASGIApp): Starlette app
            client (Client): ElasticAPM Client
        """
        self.client = client

        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Processes the whole request APM capturing.

        Args:
            request (Request)
            call_next (RequestResponseEndpoint): Next request process in Starlette.

        Returns:
            Response
        """
        await self._request_started(request)

        try:
            response = await call_next(request)
        except Exception:
            await self.capture_exception()
            elasticapm.set_transaction_result("HTTP 5xx", override=False)
            elasticapm.set_context({"status_code": 500}, "response")

            raise
        else:
            await self._request_finished(response)
        finally:
            self.client.end_transaction()

        return response

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
        trace_parent = TraceParent.from_headers(dict(request.headers))
        self.client.begin_transaction("request", trace_parent=trace_parent)

        await set_context(
            lambda: get_data_from_request(
                request,
                capture_body=self.client.config.capture_body in ("transactions", "all"),
                capture_headers=self.client.config.capture_headers,
            ),
            "request"
        )
        elasticapm.set_transaction_name("{} {}".format(request.method, request.url.path), override=False)

    async def _request_finished(self, response: Response):
        """Captures the end of the request processing to APM.

        Args:
            response (Response)
        """
        await set_context(
            lambda: get_data_from_response(response, capture_headers=self.client.config.capture_headers),
            "response"
        )

        result = "HTTP {}xx".format(response.status_code // 100)
        elasticapm.set_transaction_result(result, override=False)
