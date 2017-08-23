#!/usr/bin/env bash
pip install -U pip
pip install -r tests/requirements/lint-flake8.txt --cache-dir ${PIP_CACHE}
make flake8
echo "OK"
