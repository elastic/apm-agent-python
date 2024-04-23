#!/bin/bash
#
# Make a Python APM agent distribution
#

echo "::group::Install wheel"
pip install --user wheel
echo "::endgroup::"

echo "::group::Building universal wheel"
python setup.py bdist_wheel
echo "::endgroup::"

echo "::group::Building source distribution"
python setup.py sdist
echo "::endgroup::"
