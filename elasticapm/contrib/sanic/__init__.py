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


from __future__ import absolute_import

import logging
import sys

import elasticapm
import elasticapm.instrumentation.control
from elasticapm.base import Client
from elasticapm.conf import constants, setup_logging
from elasticapm.contrib.sanic.utils import get_data_from_request, get_data_from_response, make_client
from elasticapm.handlers.logging import LoggingHandler
from elasticapm.utils import build_name_with_http_method_prefix
from elasticapm.utils.disttracing import TraceParent

logger = logging.getLogger("elasticapm.errors.client")


class ElasticAPM(object):
    def __init__(self, app=None, client=None, client_cls=Client, logging=False, **defaults):
        self._app = app
        self._logging = logging
        self._client_cls = client_cls
        self._client = client
        self._skip_header = []
        if app:
            self.init_app(app, **defaults)

        if defaults.get("skip_headers"):
            self._skip_header = defaults.pop("skip_headers")

    @property
    def app(self):
        return self._app

    @property
    def logging(self):
        return self._logging

    @property
    def client_cls(self):
        return self._client_cls

    @property
    def client(self):
        return self._client

    @property
    def skip_headers(self):
        return self._skip_header

    def _register_exception_handler(self):
        @self.app.exception(Exception)
        def _exception_handler(request, exception):
            if not self.client:
                return

            if self.app.debug and not self.client.config.debug:
                return

            self.client.capture_exception(
                exc_info=sys.exc_info(),
                context={
                    "request": get_data_from_request(
                        request,
                        capture_body=self.client.config.capture_body in ("errors", "all"),
                        capture_headers=self.client.config.capture_headers,
                        skip_headers=self.skip_headers,
                    )
                },
                custom={"app": self.app},
                handled=False,
            )

    def _register_request_started(self):
        @self.app.middleware("request")
        def request_middleware(request):
            if not self.app.debug or self.client.config.debug:
                if constants.TRACEPARENT_HEADER_NAME in request.headers:
                    trace_parent = TraceParent.from_string(request.headers[constants.TRACEPARENT_HEADER_NAME])
                else:
                    trace_parent = None
                self.client.begin_transaction("request", trace_parent=trace_parent)

    def _register_request_finished(self):
        @self.app.middleware("response")
        def response_middleware(request, response):
            if not self.app.debug or self.client.config.debug:
                rule = request.uri_template if request.uri_template is not None else ""
                rule = build_name_with_http_method_prefix(rule, request)
                elasticapm.set_context(
                    lambda: get_data_from_request(
                        request,
                        capture_body=self.client.config.capture_body in ("transactions", "all"),
                        capture_headers=self.client.config.capture_headers,
                        skip_headers=self.skip_headers,
                    ),
                    "request",
                )

                elasticapm.set_context(
                    lambda: get_data_from_response(
                        response,
                        capture_body=self.client.config.capture_body in ("transactions", "all"),
                        capture_headers=self.client.config.capture_headers,
                        skip_headers=self.skip_headers,
                    ),
                    "response",
                )
                if response.status:
                    result = "HTTP {}xx".format(response.status // 100)
                else:
                    result = response.status
                elasticapm.set_transaction_name(rule, override=False)
                elasticapm.set_transaction_result(result, override=False)
                self.client.end_transaction(rule, result)

    def init_app(self, app, **defaults):
        self._app = app
        if not self.client:
            self._client = make_client(self.client_cls, app, **defaults)

        if self.logging or self.logging == 0:
            if self.logging is not True:
                kwargs = {"level": self.logging}
            else:
                kwargs = {}
            setup_logging(LoggingHandler(self.client, **kwargs))

        self._register_exception_handler()

        try:
            from elasticapm.contrib.celery import register_exception_tracking

            register_exception_tracking(self.client)
        except ImportError:
            pass

        if self.client.config.instrument:
            elasticapm.instrumentation.control.instrument()

            self._register_request_started()
            self._register_request_finished()
            try:
                from elasticapm.contrib.celery import register_instrumentation

                register_instrumentation(self.client)
            except ImportError:
                pass
        else:
            logger.debug("Skipping instrumentation. INSTRUMENT is set to False")

    def capture_exception(self, *args, **kwargs):
        assert self.client, "capture_exception called before application configuration is initialized"
        return self.client.capture_exception(*args, **kwargs)

    def capture_message(self, *args, **kwargs):
        assert self.client, "capture_message called before application configuration is initialized"
        return self.client.capture_message(*args, **kwargs)
