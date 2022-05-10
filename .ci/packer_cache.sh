#!/usr/bin/env bash

source /usr/local/bin/bash_standard_lib.sh

if [ -x "$(command -v docker)" ]; then
    grep "-" .ci/.jenkins_python_full.yml | cut -d'-' -f2- | \
    while read -r version;
    do
        if [[ "$version" == *"#"* ]]; then
            echo "skipped ${version}"
        else
            imageName="apm-agent-python:${version}"
            registryImageName="docker.elastic.co/observability-ci/${imageName}"
            (retry 2 docker pull "${registryImageName}") || echo 'Skip failing packer_cache'
            docker tag "${registryImageName}" "${imageName}" || echo 'Skip failing packer_cache'
        fi
    done
fi
