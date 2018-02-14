#!/usr/bin/env bash
set -e

cd tests

docker build -t "docs:python" -f ./DockerfileDocs .
docker run -e LOCAL_USER_ID=$UID \
           -v "$(dirname $(pwd))":/app \
           -i "docs:python" \
           make docs
