#!/usr/bin/env bash

set -e

pip_cache="$HOME/.cache"
docker_pip_cache="/tmp/cache/pip"

cd tests

docker build --build-arg PYTHON_IMAGE=python:3.6 -t lint_flake8 .
docker run \
  -e LOCAL_USER_ID=$UID \
  -e PIP_CACHE=${docker_pip_cache} \
  -v ${pip_cache}:$(dirname ${docker_pip_cache}) \
  -v "$(dirname $(pwd))":/app \
  -w /app \
  --rm lint_flake8 \
  /bin/bash \
  -c "pip install --user -U pip
      pip install --user -r tests/requirements/lint-flake8.txt --cache-dir ${docker_pip_cache}
      /home/user/.local/bin/flake8 elasticapm"
