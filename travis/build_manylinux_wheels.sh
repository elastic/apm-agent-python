#!/usr/bin/env bash

set -e -x

export SKIP_ZERORPC=1
export ELASTICAPM_WRAPT_EXTENSIONS="true"

# Compile wheels
for PYBIN in /opt/python/*/bin; do
    if [[ $PYBIN == *cp26* ]]; then
        continue
    fi
    ${PYBIN}/pip install -r /io/test_requirements/requirements-base.txt
    ${PYBIN}/pip install -r /io/test_requirements/requirements-python-$($PYBIN/python -c "import sys; print(sys.version_info[0])").txt
    ${PYBIN}/pip wheel /io/ -w wheelhouse/
done

# Bundle external shared libraries into the wheels
for whl in wheelhouse/opbeat*.whl; do
    auditwheel repair $whl -w /io/wheelhouse/
done

# Install packages and test
for PYBIN in /opt/python/*/bin/; do
    ${PYBIN}/pip install opbeat --no-index -f /io/wheelhouse
    (cd $HOME; ${PYBIN}/py.test)
done

chmod 0777 /io/wheelhouse/*.whl
