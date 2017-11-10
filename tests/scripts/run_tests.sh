#!/usr/bin/env bash

set -ex

pip install --user -U pip --cache-dir "${PIP_CACHE}"
pip install --user -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

export PATH=/home/user/.local/bin:$PATH

make test
