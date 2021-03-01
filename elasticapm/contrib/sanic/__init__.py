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

import sys
import typing as t

from sanic import Sanic
from sanic.request import Request
from sanic.response import HTTPResponse

from elasticapm import label
from elasticapm import set_context as elastic_context
from elasticapm import (
    set_custom_context,
    set_transaction_name,
    set_transaction_outcome,
    set_transaction_result,
    set_user_context,
)
from elasticapm.base import Client
from elasticapm.conf import constants
from elasticapm.contrib.asyncio.traces import set_context
from elasticapm.contrib.sanic.utils import get_request_info, get_response_info, make_client
from elasticapm.instrumentation.control import instrument
from elasticapm.utils.disttracing import TraceParent
from elasticapm.utils.logging import get_logger

user_info_type = t.Tuple[t.Union[None, str], t.Union[None, str], t.Union[None, str]]
label_info_type = t.Dict[str, t.Union[str, bool, int, float]]
custom_info_type = t.Dict[str, t.Any]
req_or_response_type = t.Union[Request, HTTPResponse]


class ElasticAPM:
    def __init__(
        self,
        app: Sanic,
        client: t.Union[None, Client] = None,
        client_cls: t.Type[Client] = Client,
        config: t.Union[None, t.Dict[str, t.Any]] = None,
        transaction_name_callback: t.Union[None, t.Callable[[Request], str]] = None,
        user_context_callback: t.Union[None, t.Callable[[Request], t.Awaitable[user_info_type]]] = None,
        custom_context_callback: t.Union[
            None, t.Callable[[req_or_response_type], t.Awaitable[custom_info_type]]
        ] = None,
        label_info_callback: t.Union[None, t.Callable[[req_or_response_type], t.Awaitable[label_info_type]]] = None,
        **defaults,
    ) -> None:
        self._app = app  # type: Sanic
        self._client_cls = client_cls  # type: type
        self._client = client  # type: t.Union[None, Client]
        self._skip_headers = defaults.pop("skip_headers", [])  # type: t.List[str]
        self._transaction_name_callback = transaction_name_callback  # type: t.Union[None, t.Callable[[Request], str]]
        self._user_context_callback = (
            user_context_callback
        )  # type: t.Union[None, t.Callable[[Request], t.Awaitable[user_info_type]]]
        self._custom_context_callback = (
            custom_context_callback
        )  # type: t.Union[None, t.Callable[[req_or_response_type], t.Awaitable[custom_info_type]]]
        self._label_info_callback = (
            label_info_callback
        )  # type: t.Union[None, t.Callable[[req_or_response_type], t.Awaitable[label_info_type]]]
        self._logger = get_logger("elasticapm.errors.client")
        self._init_app(config=config, **defaults)

    async def capture_exception(self, *args, **kwargs):
        assert self._client, "capture_exception called before application configuration is initialized"
        return self._client.capture_exception(*args, **kwargs)

    async def capture_message(self, *args, **kwargs):
        assert self._client, "capture_message called before application configuration is initialized"
        return self._client.capture_message(*args, **kwargs)

    # noinspection PyBroadException
    def _init_app(self, config: t.Union[None, t.Dict[str, t.Any]], **defaults) -> None:
        if not self._client:
            cfg = config or self._app.config.get("ELASTIC_APM")
            self._client = make_client(config=cfg, client_cls=self._client_cls, **defaults)

        self._setup_exception_manager()

        if self._client.config.instrument and self._client.config.enabled:
            instrument()
            try:
                from elasticapm.contrib.celery import register_instrumentation

                register_instrumentation(client=self._client)
            except ImportError:
                self._logger.debug(
                    "Failed to setup instrumentation. "
                    "Please install requirements for elasticapm.contrib.celery if instrumentation is required"
                )
                pass

        self._setup_request_handler()

    # noinspection PyMethodMayBeStatic
    def _default_transaction_name_generator(self, request: Request) -> str:
        name = request.endpoint
        return f"{request.method}_{name}"

    def _setup_request_handler(self):
        @self._app.middleware("request")
        async def _instrument_request(request: Request):
            if not self._client.should_ignore_url(url=request.path):
                trace_parent = TraceParent.from_headers(headers=request.headers)
                self._client.begin_transaction("request", trace_parent=trace_parent)
                await set_context(
                    lambda: get_request_info(
                        config=self._client.config, request=request, skip_headers=self._skip_headers
                    ),
                    "request",
                )
                self._setup_transaction_name(request=request)
                if self._user_context_callback:
                    name, email, uid = await self._user_context_callback(request)
                    set_user_context(username=name, email=email, user_id=uid)

                if self._custom_context_callback:
                    set_custom_context(data=await self._custom_context_callback(request))

                if self._label_info_callback:
                    labels = await self._label_info_callback(request)
                    label(**labels)

        # noinspection PyUnusedLocal
        @self._app.middleware("response")
        async def _instrument_response(request: Request, response: HTTPResponse):
            await set_context(
                lambda: get_response_info(
                    config=self._client.config,
                    response=response,
                    skip_headers=self._skip_headers,
                ),
                "response",
            )
            self._setup_transaction_name(request=request)
            result = f"HTTP {response.status // 100}xx"
            set_transaction_result(result=result, override=False)
            set_transaction_outcome(http_status_code=response.status, override=False)
            elastic_context(data={"status_code": response.status}, key="response")
            self._client.end_transaction()

    def _setup_transaction_name(self, request: Request) -> None:
        if self._transaction_name_callback:
            name = self._transaction_name_callback(request)
        else:
            name = self._default_transaction_name_generator(request=request)
        if name:
            set_transaction_name(name, override=False)

    # noinspection PyBroadException
    def _setup_exception_manager(self):
        # noinspection PyUnusedLocal
        @self._app.exception(Exception)
        async def _handler(request: Request, exception: Exception):
            if not self._client:
                return

            self._client.capture_exception(
                exc_info=sys.exc_info(),
                context={
                    "request": await get_request_info(
                        config=self._client.config, request=request, skip_headers=self._skip_headers
                    ),
                },
                custom={"app": self._app},
                handled=False,
            )
            self._setup_transaction_name(request=request)
            set_transaction_result(result="HTTP 5xx", override=False)
            set_transaction_outcome(outcome=constants.OUTCOME.FAILURE, override=False)
            elastic_context(data={"status_code": 500}, key="response")
            self._client.end_transaction()

        try:
            from elasticapm.contrib.celery import register_exception_tracking

            register_exception_tracking(client=self._client)
        except ImportError:
            self._logger.debug(
                "Failed to setup Exception tracking. "
                "Please install requirements for elasticapm.contrib.celery if exception tracking is required"
            )
            pass
