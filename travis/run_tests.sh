#!/usr/bin/env bash

set -ex

PYTHON_MAJOR_VERSION=$(python -c "import sys; print(sys.version_info[0])");
mkdir -p "$PIP_CACHE"
mkdir -p wheelhouse
psql -c 'create database elasticapm_test;' -U postgres
export POSTGRES_DB=elasticapm_test
pip install -U pip codecov
pip install -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/requirements-python-${PYTHON_MAJOR_VERSION}.txt" --cache-dir "${PIP_CACHE}"
if [[ $TRAVIS_PYTHON_VERSION =~ ^(3.5|3.6|nightly)$ ]]; then
  pip install -r tests/requirements/requirements-asyncio.txt --cache-dir "${PIP_CACHE}"
fi
if [[ $TRAVIS_PYTHON_VERSION == 'pypy' ]]; then
  pip install -r tests/requirements/requirements-pypy.txt --cache-dir "${PIP_CACHE}"
else
  pip install -r tests/requirements/requirements-cpython.txt --cache-dir "${PIP_CACHE}"
  if [[ $PYTHON_MAJOR_VERSION == '2' ]]; then
    pip install -r tests/requirements/requirements-zerorpc.txt --cache-dir "${PIP_CACHE}"
  fi
fi

make coverage
codecov