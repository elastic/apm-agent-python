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

import os
import re

CGROUP_PATH = "/proc/self/cgroup"

SYSTEMD_SCOPE_SUFFIX = ".scope"

kubepods_regexp = re.compile(
    r"(?:^/kubepods/[^/]+/pod([^/]+)$)|(?:^/kubepods\.slice/kubepods-[^/]+\.slice/kubepods-[^/]+-pod([^/]+)\.slice$)"
)

container_id_regexp = re.compile(
    "^(?:[0-9a-f]{64}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4,})$", re.IGNORECASE
)


def get_cgroup_container_metadata():
    """
    Reads docker/kubernetes metadata (container id, pod id) from /proc/self/cgroup

    The result is a nested dictionary with the detected IDs, e.g.

        {
            "container": {"id": "2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63"},
            "pod": {"uid": "90d81341_92de_11e7_8cf2_507b9d4141fa"}
        }

    :return: a dictionary with the detected ids or {}
    """
    if not os.path.exists(CGROUP_PATH):
        return {}
    with open(CGROUP_PATH) as f:
        return parse_cgroups(f) or {}


def parse_cgroups(filehandle):
    """
    Reads lines from a file handle and tries to parse docker container IDs and kubernetes Pod IDs.

    See tests.utils.docker_tests.test_cgroup_parsing for a set of test cases

    :param filehandle:
    :return: nested dictionary or None
    """
    for line in filehandle:
        parts = line.strip().split(":")
        if len(parts) != 3:
            continue
        cgroup_path = parts[2]

        # Depending on the filesystem driver used for cgroup
        # management, the paths in /proc/pid/cgroup will have
        # one of the following formats in a Docker container:
        #
        #   systemd: /system.slice/docker-<container-ID>.scope
        #   cgroupfs: /docker/<container-ID>
        #
        # In a Kubernetes pod, the cgroup path will look like:
        #
        #   systemd:/kubepods.slice/kubepods-<QoS-class>.slice/kubepods-<QoS-class>-pod<pod-UID>.slice/<container-iD>.scope
        #   cgroupfs:/kubepods/<QoS-class>/pod<pod-UID>/<container-iD>

        directory, container_id = os.path.split(cgroup_path)
        if container_id.endswith(SYSTEMD_SCOPE_SUFFIX):
            container_id = container_id[: -len(SYSTEMD_SCOPE_SUFFIX)]
            if "-" in container_id:
                container_id = container_id.split("-", 1)[1]
        kubepods_match = kubepods_regexp.match(directory)
        if kubepods_match:
            pod_id = kubepods_match.group(1)
            if not pod_id:
                pod_id = kubepods_match.group(2)
                if pod_id:
                    pod_id = pod_id.replace("_", "-")
            return {"container": {"id": container_id}, "kubernetes": {"pod": {"uid": pod_id}}}
        elif container_id_regexp.match(container_id):
            return {"container": {"id": container_id}}
