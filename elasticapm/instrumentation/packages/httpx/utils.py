#  BSD 3-Clause License
#
#  Copyright (c) 2021, Elasticsearch BV
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
from typing import Tuple

from elasticapm.conf import constants


def get_request_data(args, kwargs) -> Tuple[Tuple[str, str, int, str], str, list]:
    if len(args) == 1 and hasattr(args[0], "method"):
        # httpcore >= 0.14
        request = args[0]
        method = request.method.decode("utf-8")
        headers = request.headers
        url = (
            request.url.scheme.decode("utf-8"),
            request.url.host.decode("utf-8"),
            request.url.port,
            request.url.target.decode("utf-8"),
        )
    else:
        if "method" in kwargs:
            method = kwargs["method"].decode("utf-8")
        else:
            method = args[0].decode("utf-8")

        # URL is a tuple of (scheme, host, port, path)
        if "url" in kwargs:
            url = kwargs["url"]
        else:
            url = args[1]
        url = (url[0].decode("utf-8"), url[1].decode("utf-8"), url[2], url[3].decode("utf-8"))
        if "headers" in kwargs:
            headers = kwargs["headers"]
        else:
            headers = []
    return url, method, headers


def get_status(response) -> int:
    if hasattr(response, "status"):  # httpcore >= 0.14
        status_code = response.status
    elif len(response) > 4:
        # httpcore < 0.11.0
        # response = (http_version, status_code, reason_phrase, headers, stream)
        status_code = response[1]
    else:
        # httpcore >= 0.11.0
        # response = (status_code, headers, stream, ext)
        status_code = response[0]
    return status_code


def set_disttracing_headers(headers, trace_parent, transaction):
    trace_parent_str = trace_parent.to_string()
    headers.append((bytes(constants.TRACEPARENT_HEADER_NAME, "utf-8"), bytes(trace_parent_str, "utf-8")))
    if transaction.tracer.config.use_elastic_traceparent_header:
        headers.append((bytes(constants.TRACEPARENT_LEGACY_HEADER_NAME, "utf-8"), bytes(trace_parent_str, "utf-8")))
    if trace_parent.tracestate:
        headers.append((bytes(constants.TRACESTATE_HEADER_NAME, "utf-8"), bytes(trace_parent.tracestate, "utf-8")))
