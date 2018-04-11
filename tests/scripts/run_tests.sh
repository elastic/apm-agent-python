#!/usr/bin/env bash

set -ex

pip install --user -U pip --cache-dir "${PIP_CACHE}"
pip install --user -r "tests/requirements/requirements-${WEBFRAMEWORK}.txt" --cache-dir "${PIP_CACHE}"

export PATH=/home/user/.local/bin:$PATH

export PYTHON_VERSION=$(python -c "import platform; pv=platform.python_version_tuple(); print('pypy' + ('' if pv[0] == 2 else str(pv[0])) if platform.python_implementation() == 'PyPy' else '.'.join(map(str, platform.python_version_tuple()[:2])))")

make update-json-schema

if [[ "$WITH_COVERAGE" == "true" ]]
then
    make coverage
else
    make test
fi
