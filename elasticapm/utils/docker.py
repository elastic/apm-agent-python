import os
import re

DOCKER_ID_PATH = "/proc/self/cgroup"


def docker_id():
    if not os.path.exists(DOCKER_ID_PATH):
        return
    with open(DOCKER_ID_PATH) as f:
        return parse_cgroups(f)


def parse_cgroups(filehandle):
    for line in filehandle:
        try:
            if "docker" not in line and "kubepods" not in line:
                continue
            parts = line.split(":")
            for part in parts:
                if "docker" in part:
                    docker_id = part.split("/")[-1]
                    # older docker versions prepend "docker-" and append ".scope"
                    if "-" in docker_id:
                        docker_id = re.split("[.-]", docker_id)[1]
                    return {"container": {"id": docker_id}}
                elif "kubepods" in part:
                    pod_id, docker_id = part.split("/")[-2:]
                    if "pod" in pod_id:
                        pod_id = pod_id[pod_id.rindex("pod") + 3 :]
                    if pod_id.endswith(".slice"):
                        pod_id = pod_id[:-6]
                    if docker_id.endswith(".scope"):
                        docker_id = re.split("[.-]", docker_id)[1]
                    return {"container": {"id": docker_id}, "pod": {"uid": pod_id}}
        except IndexError:
            pass
