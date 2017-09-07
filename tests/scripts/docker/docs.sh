#!/usr/bin/env bash
set -e

docker build -t "lint-docs" -f ./DockerfileDocs .
docker run -i "lint-docs"
