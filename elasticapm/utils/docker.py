import os
import re

DOCKER_ID_PATH = "/proc/self/cgroup"


def get_docker_metadata():
    """
    Reads docker/kubernetes metadata (container id, pod id) from /proc/self/cgroup

    The result is a nested dictionary with the detected IDs, e.g.

        {
            "container": {"id": "2227daf62df6694645fee5df53c1f91271546a9560e8600a525690ae252b7f63"},
            "pod": {"uid": "90d81341_92de_11e7_8cf2_507b9d4141fa"}
        }

    :return: a dictionary with the detected ids or {}
    """
    if not os.path.exists(DOCKER_ID_PATH):
        return {}
    with open(DOCKER_ID_PATH) as f:
        return parse_cgroups(f) or {}


def parse_cgroups(filehandle):
    """
    Reads lines from a file handle and tries to parse docker container IDs and kubernetes Pod IDs.

    See tests.utils.docker_tests.test_cgroup_parsing for a set of test cases

    :param filehandle:
    :return: nested dictionary or None
    """
    for line in filehandle:
        try:
            if "docker" not in line and "kubepods" not in line:
                continue
            parts = line.split(":")
            for part in parts:
                if "docker" in part:
                    container_id = part.split("/")[-1]
                    # older docker versions prepend "docker-" and append ".scope"
                    if "-" in container_id:
                        container_id = re.split("[.-]", container_id)[1]
                    return {"container": {"id": container_id}}
                elif "kubepods" in part:
                    pod_id, container_id = part.split("/")[-2:]
                    if "pod" in pod_id:
                        pod_id = pod_id[pod_id.rindex("pod") + 3 :]
                    if pod_id.endswith(".slice"):
                        pod_id = pod_id[:-6]
                    if container_id.endswith(".scope"):
                        container_id = re.split("[.-]", container_id)[1]
                    return {"container": {"id": container_id}, "pod": {"uid": pod_id}}
        except IndexError:
            pass
