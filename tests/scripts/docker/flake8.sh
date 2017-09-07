#!/usr/bin/env bash

set -e

pip_cache="$HOME/.cache/pip"
docker_pip_cache="/app/.cache/pip"

docker build --build-arg PYTHON_IMAGE=python:3.6 -t lint_flake8 .
docker run \
  -e PIP_CACHE=${docker_pip_cache} \
  -v ${pip_cache}:${docker_pip_cache} \
  -w /app \
  --rm lint_flake8 \
  /bin/bash \
  -c "pip install -U pip
      pip install -r tests/requirements/lint-flake8.txt --cache-dir ${docker_pip_cache}
      make flake8"
