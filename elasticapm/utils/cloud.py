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

import json

import urllib3


def guess_provider():
    """
    Use low-hanging fruit methods to try to guess which cloud provider is
    hosting this server.
    """
    raise NotImplementedError()


def aws_metadata():
    """
    Fetch AWS metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    ret = {}

    try:
        ttl_header = {"X-aws-ec2-metadata-token-ttl-seconds": "300"}
        token_url = "http://169.254.169.254/latest/api/token"
        token_request = urllib3.request("PUT", token_url, headers=ttl_header, timeout=3.0)
        token = token_request.data.decode("utf-8")
        aws_token_header = {"X-aws-ec2-metadata-token": token}
        r = json.loads(
            urllib3.request(
                "GET",
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers=aws_token_header,
                timeout=3,
            ).data.decode("utf-8")
        )

        ret = {
            "account": {"id": r["accountId"]},
            "instance": {"id": r["instanceId"]},
            "availability_zone": r["availabilityZone"],
            "machine": {"type": r["instanceType"]},
            "provider": "aws",
            "region": r["region"],
        }
    except Exception:
        # Not on an AWS box
        return {}
    return ret


def gcp_metadata():
    """
    Fetch GCP metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    raise NotImplementedError()


def azure_metadata():
    """
    Fetch Azure metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    raise NotImplementedError()
