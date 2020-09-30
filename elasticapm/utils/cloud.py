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
import os
import socket

import urllib3


def aws_metadata():
    """
    Fetch AWS metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    http = urllib3.PoolManager()

    try:
        # This will throw an error if the metadata server isn't available,
        # and will be quiet in the logs, unlike urllib3
        socket.create_connection(("169.254.169.254", 80), 0.1)

        try:
            # This whole block is almost unnecessary. IMDSv1 will be supported
            # indefinitely, so the only time this block is needed is if a
            # security-conscious user has set the metadata service to require
            # IMDSv2. Thus, the very expansive try:except: coverage.

            # TODO: should we have a config option to completely disable IMDSv2 to reduce overhead?
            ttl_header = {"X-aws-ec2-metadata-token-ttl-seconds": "300"}
            token_url = "http://169.254.169.254/latest/api/token"
            token_request = http.request("PUT", token_url, headers=ttl_header, timeout=1.0, retries=False)
            token = token_request.data.decode("utf-8")
            aws_token_header = {"X-aws-ec2-metadata-token": token} if token else {}
        except Exception:
            aws_token_header = {}
        metadata = json.loads(
            http.request(
                "GET",
                "http://169.254.169.254/latest/dynamic/instance-identity/document",
                headers=aws_token_header,
                timeout=1.0,
                retries=False,
            ).data.decode("utf-8")
        )

        return {
            "account": {"id": metadata["accountId"]},
            "instance": {"id": metadata["instanceId"]},
            "availability_zone": metadata["availabilityZone"],
            "machine": {"type": metadata["instanceType"]},
            "provider": "aws",
            "region": metadata["region"],
        }

    except Exception:
        # Not on an AWS box
        return {}


def gcp_metadata():
    """
    Fetch GCP metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    headers = {"Metadata-Flavor": "Google"}
    http = urllib3.PoolManager()

    try:
        # This will throw an error if the metadata server isn't available,
        # and will be quiet in the logs, unlike urllib3
        socket.getaddrinfo("metadata.google.internal", 80, 0, socket.SOCK_STREAM)

        metadata = json.loads(
            http.request(
                "GET",
                "http://metadata.google.internal/computeMetadata/v1/?recursive=true",
                headers=headers,
                timeout=1.0,
                retries=False,
            ).data.decode("utf-8")
        )

        availability_zone = os.path.split(metadata["instance"]["zone"])[1]

        return {
            "provider": "gcp",
            "instance": {"id": str(metadata["instance"]["id"]), "name": metadata["instance"]["name"]},
            "project": {"id": str(metadata["project"]["numericProjectId"]), "name": metadata["project"]["projectId"]},
            "availability_zone": availability_zone,
            "region": availability_zone.rsplit("-", 1)[0],
            "machine": {"type": metadata["instance"]["machineType"].split("/")[-1]},
        }

    except Exception:
        # Not on a gcp box
        return {}


def azure_metadata():
    """
    Fetch Azure metadata from the local metadata server. If metadata server is
    not found, return an empty dictionary
    """
    headers = {"Metadata": "true"}
    http = urllib3.PoolManager()

    try:
        # This will throw an error if the metadata server isn't available,
        # and will be quiet in the logs, unlike urllib3
        socket.create_connection(("169.254.169.254", 80), 0.1)

        # Can't use newest metadata service version, as it's not guaranteed
        # to be available in all regions
        metadata = json.loads(
            http.request(
                "GET",
                "http://169.254.169.254/metadata/instance/compute?api-version=2019-08-15",
                headers=headers,
                timeout=1.0,
                retries=False,
            ).data.decode("utf-8")
        )

        ret = {
            "account": {"id": metadata["subscriptionId"]},
            "instance": {"id": metadata["vmId"], "name": metadata["name"]},
            "project": {"name": metadata["resourceGroupName"]},
            "availability_zone": metadata["zone"],
            "machine": {"type": metadata["vmSize"]},
            "provider": "azure",
            "region": metadata["location"],
        }

        if not ret["availability_zone"]:
            ret.pop("availability_zone")
        return ret

    except Exception:
        # Not on an Azure box
        return {}
