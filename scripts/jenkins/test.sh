#!/usr/bin/env bash

set -euxo pipefail

echo "Python: ${PYTHON_VERSION} - ${WEBFRAMEWORK}"

pip install -U pip codecov --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

make update-json-schema
make test
