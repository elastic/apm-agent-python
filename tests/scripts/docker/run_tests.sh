#!/usr/bin/env bash
if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi

pip_cache=${3-"$HOME/.cache/pip"}
docker_pip_cache="/app/.cache/pip"
mkdir -p ${pip_cache}

export PYTHON_IMAGE=$1

PYTHON_TYPE="python"
if [[ $1 == *"pypy"*  ]]; then
  PYTHON_TYPE="pypy"
fi

docker-compose pull run_tests
docker-compose run \
  -e WEBFRAMEWORK=$2 -e PIP_CACHE=${docker_pip_cache} -e PYTHON_TYPE=$PYTHON_TYPE \
  -v `pwd`:/app -v ${pip_cache}:${docker_pip_cache} \
  --rm run_tests
