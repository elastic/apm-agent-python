#!/usr/bin/env bash
label=${1-"build_no=1"}
tag="lint-docs"

docker build --label ${label}  -t ${tag} -f ./DockerfileDocs .
docker run -i ${tag}
