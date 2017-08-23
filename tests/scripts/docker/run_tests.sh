#!/usr/bin/env bash
if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi
python_version=${1}
webframework=${2}

pip_cache=${3-"$HOME/.cache/pip"}
docker_pip_cache="/app/.cache/pip"
mkdir -p ${pip_cache}

docker-compose build --build-arg PYTHON_VERSION=${python_version} run_tests
docker-compose run -e WEBFRAMEWORK=${webframework} -e PIP_CACHE=${pip_cache} -v `pwd`:/app -v ${pip_cache}:${docker_pip_cache} --rm run_tests
