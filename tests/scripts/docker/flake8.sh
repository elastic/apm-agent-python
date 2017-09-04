#!/usr/bin/env bash
pip_cache=${1-"$HOME/.cache/pip"}
docker_pip_cache="/app/.cache/pip"

mkdir -p ${pip_cache}

docker run \
  -e PIP_CACHE=${docker_pip_cache} \
  -v `pwd`:/app -v ${pip_cache}:${docker_pip_cache} \
  -w /app \
  python:3.6 \
  /bin/bash \
  -c "pip install -U pip
      pip install -r tests/requirements/lint-flake8.txt --cache-dir ${docker_pip_cache}
      make flake8"
