#!/usr/bin/env bash

set -ex

pip install -U pip codecov --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/reqs-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

export PYTHON_VERSION=$TRAVIS_PYTHON_VERSION

make update-json-schema
make test
