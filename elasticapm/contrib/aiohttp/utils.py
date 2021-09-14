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
from typing import Union

from aiohttp.web import HTTPException, Request, Response

from elasticapm.conf import Config
from elasticapm.utils import compat, get_url_dict


def get_data_from_request(request: Request, config: Config, event_type: str):
    result = {
        "method": request.method,
        "socket": {"remote_address": request.remote, "encrypted": request.secure},
        "cookies": dict(request.cookies),
    }
    if config.capture_headers:
        result["headers"] = dict(request.headers)

    # TODO: capture body

    result["url"] = get_url_dict(str(request.url))
    return result


def get_data_from_response(response: Union[HTTPException, Response], config: Config, event_type: str):
    result = {}
    status = getattr(response, "status", getattr(response, "status_code", None))
    if isinstance(status, compat.integer_types):
        result["status_code"] = status
    if config.capture_headers and getattr(response, "headers", None):
        headers = response.headers
        result["headers"] = {key: ";".join(headers.getall(key)) for key in compat.iterkeys(headers)}
    return result
