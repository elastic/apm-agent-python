#!/usr/bin/env bash
set -ex

cd tests
docker build --pull --force-rm --build-arg PYTHON_IMAGE=${1/-/:} -t apm-agent-python:${1} . # replace - with : to get the correct docker image
