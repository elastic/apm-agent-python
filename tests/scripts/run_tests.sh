#!/usr/bin/env bash

set -ex

pip install -U pip --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

make test
