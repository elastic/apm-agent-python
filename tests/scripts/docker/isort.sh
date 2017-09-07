#!/usr/bin/env bash

set -e

pip_cache="$HOME/.cache/pip"
docker_pip_cache="/app/.cache/pip"

docker build --build-arg PYTHON_IMAGE=python:3.6 -t lint_isort .
docker run \
  -e PIP_CACHE=${docker_pip_cache} \
  -v ${pip_cache}:${docker_pip_cache} \
  -w /app \
  --rm lint_isort \
  /bin/bash \
  -c "pip install -U pip 
      pip install -r tests/requirements/lint-isort.txt --cache-dir ${docker_pip_cache}
      isort -c -df"
