#!/usr/bin/env bash

set -ex

mkdir -p "$PIP_CACHE"
mkdir -p wheelhouse
psql -c 'create database elasticapm_test;' -U postgres
export POSTGRES_DB=elasticapm_test
pip install -U pip codecov --cache-dir "${PIP_CACHE}"
pip install -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

make coverage
codecov