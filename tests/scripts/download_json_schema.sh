#!/usr/bin/env bash

set -ex

download_schema()
{
    rm -rf ${1} && mkdir -p ${1}
    for run in 1 2 3 4 5
    do
        if [ -x "$(command -v gtar)" ]; then
            curl --silent --fail https://codeload.github.com/elastic/apm-server/tar.gz/${2} | gtar xzvf - --directory=${1} --strip-components=1 "*/docs/spec/*"
        else
            curl --silent --fail https://codeload.github.com/elastic/apm-server/tar.gz/${2} | tar xzvf - --directory=${1} --strip-components=1 "*/docs/spec/*"
        fi
        result=$?
        if [ $result -eq 0 ]; then break; fi
        sleep 1
    done

    if [ $result -ne 0 ]; then exit $result; fi

    mv -f ${1}/docs/spec/* ${1}/
    rm -rf ${1}/docs
}

# parent directory
basedir=$(dirname "$0")/..


download_schema ${basedir}/.schemacache master

echo "Done."
