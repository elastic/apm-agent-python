#!/usr/bin/env bash

source /usr/local/bin/bash_standard_lib.sh

grep "-" .ci/.jenkins_python.yml | cut -d'-' -f2- | \
while read -r version;
do
    (retry 2 ./tests/scripts/docker/docker_build.sh "${version}") || echo "Error building ${version} Docker image, we continue"
done
