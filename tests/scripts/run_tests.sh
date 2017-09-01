#!/usr/bin/env bash

set -ex

PYTHON_MAJOR_VERSION=$(python -c "import sys; print(sys.version_info[0])");
pip install -U pip
pip install -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/requirements-python-${PYTHON_MAJOR_VERSION}.txt" --cache-dir "${PIP_CACHE}"
if [[ $PYTHON_VERSION == 3.5* ]]; then
  pip install -r tests/requirements/requirements-asyncio.txt --cache-dir "${PIP_CACHE}"
fi
if [[ $PYTHON_TYPE == 'pypy' ]]; then
  pip install -r tests/requirements/requirements-pypy.txt --cache-dir "${PIP_CACHE}"
else
  pip install -r tests/requirements/requirements-cpython.txt --cache-dir "${PIP_CACHE}"
  if [[ $PYTHON_MAJOR_VERSION == '2' ]]; then
    pip install -r tests/requirements/requirements-zerorpc.txt --cache-dir "${PIP_CACHE}"
  fi
fi

make test
