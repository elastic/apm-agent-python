#!/usr/bin/env bash
label=${1-"build_no=1"}
pip_cache=${2-"$HOME/.cache/pip"}
docker_pip_cache="/app/.cache/pip"
tag="lint-flake8"

mkdir -p ${pip_cache}

docker build --label label -t ${tag} -f ./DockerfileLint .
docker run -e SCRIPT=flake8.sh -e PIP_CACHE=${docker_pip_cache} -v ${pip_cache}:${docker_pip_cache} -i ${tag}
