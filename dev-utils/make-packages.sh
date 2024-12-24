#!/bin/bash
#
# Make a Python APM agent distribution
#

echo "::group::Install build"
pip install --user build
echo "::endgroup::"

echo "::group::Building packages"
python -m build
echo "::endgroup::"
