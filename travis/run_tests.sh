#!/usr/bin/env bash
PYTHON_MAJOR_VERSION=$(python -c "import sys; print(sys.version_info[0])");
mkdir -p $PIP_CACHE
psql -c 'create database opbeat_test;' -U postgres
pip install -U pip
pip install -r test_requirements/requirements-${WEBFRAMEWORK}.txt --cache-dir ${PIP_CACHE}
pip install -r test_requirements/requirements-python-${PYTHON_MAJOR_VERSION}.txt --cache-dir ${PIP_CACHE}
if [[ $TRAVIS_PYTHON_VERSION == '3.5' ]]; then
  pip install -r test_requirements/requirements-asyncio.txt --cache-dir ${PIP_CACHE};
fi
if [[ $TRAVIS_PYTHON_VERSION != 'pypy' ]]; then
  pip install -r test_requirements/requirements-cpython.txt --cache-dir ${PIP_CACHE};
  if [[ $PYTHON_MAJOR_VERSION == '2' ]]; then
    pip install -r test_requirements/requirements-zerorpc.txt --cache-dir ${PIP_CACHE};
  fi
fi
if [[ $TRAVIS_PYTHON_VERSION == 'pypy' ]]; then
  pip install -r test_requirements/requirements-pypy.txt --cache-dir ${PIP_CACHE};
fi

make test