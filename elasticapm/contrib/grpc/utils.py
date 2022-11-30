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

import grpc

from elasticapm.conf.constants import OUTCOME

# see https://github.com/elastic/apm/blob/cf182bcfbe35b8586/specs/agents/tracing-instrumentation-grpc.md#outcome

STATUS_TO_OUTCOME = {
    grpc.StatusCode.OK: OUTCOME.SUCCESS,
    grpc.StatusCode.CANCELLED: OUTCOME.SUCCESS,  # Operation cancelled by client
    grpc.StatusCode.UNKNOWN: OUTCOME.FAILURE,  # Error of an unknown type, but still an error
    grpc.StatusCode.INVALID_ARGUMENT: OUTCOME.SUCCESS,  # Client-side error
    grpc.StatusCode.DEADLINE_EXCEEDED: OUTCOME.FAILURE,
    grpc.StatusCode.NOT_FOUND: OUTCOME.SUCCESS,  # Client-side error (similar to HTTP 404)
    grpc.StatusCode.ALREADY_EXISTS: OUTCOME.SUCCESS,  # Client-side error (similar to HTTP 409)
    grpc.StatusCode.PERMISSION_DENIED: OUTCOME.SUCCESS,  # Client authentication (similar to HTTP 403)
    grpc.StatusCode.RESOURCE_EXHAUSTED: OUTCOME.FAILURE,  # Likely used for server out of resources
    grpc.StatusCode.FAILED_PRECONDITION: OUTCOME.FAILURE,  # Similar to UNAVAILABLE
    grpc.StatusCode.ABORTED: OUTCOME.FAILURE,  # Similar to UNAVAILABLE
    grpc.StatusCode.OUT_OF_RANGE: OUTCOME.SUCCESS,  # Client-side error (similar to HTTP 416)
    grpc.StatusCode.UNIMPLEMENTED: OUTCOME.SUCCESS,  # Client called a non-implemented feature
    grpc.StatusCode.INTERNAL: OUTCOME.FAILURE,  # Internal error (similar to HTTP 500)
    grpc.StatusCode.UNAVAILABLE: OUTCOME.FAILURE,  # Transient error, client may retry with backoff
    grpc.StatusCode.DATA_LOSS: OUTCOME.FAILURE,  # Lost data should always be reported
    grpc.StatusCode.UNAUTHENTICATED: OUTCOME.SUCCESS,  # Client-side authentication (similar to HTTP 401)
}
