#!/usr/bin/env bash
docker build -t "lint-docs" -f ./DockerfileDocs .
docker run -i "lint-docs"
