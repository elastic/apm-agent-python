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
        resp = json.loads(
            urllib3.request(
                "GET",
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers=aws_token_header,
                timeout=3.0,
            ).data.decode("utf-8")
        )

        ret = {
            "account": {"id": resp["accountId"]},
            "instance": {"id": resp["instanceId"]},
            "availability_zone": resp["availabilityZone"],
            "machine": {"type": resp["instanceType"]},
            "provider": "aws",
            "region": resp["region"],
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
    ret = {}
    headers = {"Metadata-Flavor": "Google"}

    try:
        ret["provider"] = "gcp"
        # TODO can we get this all in one payload?
        instance_id = json.loads(
            urllib3.request(
                "GET", "http://metadata.google.internal/computeMetadata/v1/instance/id", headers=headers, timeout=3.0,
            )
        ).data.decode("utf-8")
        instance_name = json.loads(
            urllib3.request(
                "GET", "http://metadata.google.internal/computeMetadata/v1/instance/name", headers=headers, timeout=3.0,
            )
        ).data.decode("utf-8")
        ret["instance"] = {"id": instance_id, "name": instance_name}

        project_id = json.loads(
            urllib3.request(
                "GET",
                "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id",
                headers=headers,
                timeout=3.0,
            )
        ).data.decode("utf-8")
        project_name = json.loads(
            urllib3.request(
                "GET",
                "http://metadata.google.internal/computeMetadata/v1/project/project-id",
                headers=headers,
                timeout=3.0,
            )
        ).data.decode("utf-8")
        ret["project"] = {"id": project_id, "name": project_name}

        ret["availability_zone"] = json.loads(
            urllib3.request(
                "GET", "http://metadata.google.internal/computeMetadata/v1/instance/zone", headers=headers, timeout=3.0,
            )
        ).data.decode("utf-8")

        # TODO parse out just the region from the fully qualified zone
        ret["region"] = ret["availability_zone"]

        machine_type = json.loads(
            urllib3.request(
                "GET",
                "http://metadata.google.internal/computeMetadata/v1/instance/machine-type",
                headers=headers,
                timeout=3.0,
            )
        ).data.decode("utf-8")
        ret["machine"] = {"type": machine_type}

        # TODO should we use the project information for account.id and account.name?

    except Exception:
        # Not on a gcp box
        return {}

    return ret


def azure_metadata():
    """
    Fetch Azure metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    ret = {}
    headers = {"Metadata": "true"}

    try:
        # Can't use newest metadata service version, as it's not guaranteed
        # to be available in all regions
        resp = json.loads(
            urllib3.request(
                "GET",
                "http://169.254.169.254/metadata/instance/compute?api-version=2019-08-15",
                headers=headers,
                timeout=3.0,
            )
        ).data.decode("utf-8")

        ret = {
            "account": {"id": resp["subscriptionId"]},
            "instance": {"id": resp["vmId"], "name": resp["name"]},
            "project": {"name": resp["resourceGroupName"]},
            "availability_zone": resp["zone"],
            "machine": {"type": resp["vmSize"]},
            "provider": "azure",
            "region": resp["location"],
        }

    except Exception:
        # Not on an Azure box
        return {}

    return ret
