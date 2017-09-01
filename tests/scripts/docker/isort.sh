#!/usr/bin/env bash
pip_cache=${1-"$HOME/.cache/pip"}
docker_pip_cache="/app/.cache/pip"

mkdir -p ${pip_cache}

docker pull python:3.6
docker run \
  -e PIP_CACHE=${pip_cache} \
  -v `pwd`:/app -v ${pip_cache}:${docker_pip_cache} \
  -w /app \
  -i python:3.6 \
  /app/tests/scripts/isort.sh
