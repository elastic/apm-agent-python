#!/usr/bin/env bash
set -e

cd tests

docker build -t "lint-docs" -f ./DockerfileDocs .
docker run -e LOCAL_USER_ID=$UID \
           -v "$(dirname $(pwd))":/app \
           -i "lint-docs" \
           make docs
