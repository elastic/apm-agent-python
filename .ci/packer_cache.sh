#!/usr/bin/env bash

source /usr/local/bin/bash_standard_lib.sh

if [ -x "$(command -v docker)" ]; then
    grep "-" .ci/.jenkins_python_full.yml | cut -d'-' -f2- | \
    while read -r version;
    do
        imageName="apm-agent-python:${version}"
        registryImageName="docker.elastic.co/observability-ci/${imageName}"
        (retry 2 docker pull "${registryImageName}") || echo 'Skip failing packer_cache'
        docker tag "${registryImageName}" "${imageName}"
    done
fi
