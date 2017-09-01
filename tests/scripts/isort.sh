#!/usr/bin/env bash
pip install -U pip
pip install -r tests/requirements/lint-isort.txt --cache-dir ${PIP_CACHE}
isort -c -df 
