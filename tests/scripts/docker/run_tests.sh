#!/usr/bin/env bash
if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi

pip_cache="$HOME/.cache/pip"
docker_pip_cache="/app/.cache/pip"

PYTHON_TYPE="python"
if [[ $1 == *"pypy"*  ]]; then
  PYTHON_TYPE="pypy"
fi

docker-compose build --build-arg PYTHON_IMAGE=$1 run_tests
docker-compose run \
  -e PYTHONDONTWRITEBYTECODE=1 -e WEBFRAMEWORK=$2 -e PIP_CACHE=${docker_pip_cache} -e PYTHON_TYPE=$PYTHON_TYPE \
  -v ${pip_cache}:${docker_pip_cache} \
  --rm run_tests \
	/bin/bash \
  -c "./tests/scripts/run_tests.sh"
