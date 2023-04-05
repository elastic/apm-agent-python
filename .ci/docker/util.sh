#!/usr/bin/env bash

set -euo pipefail

export DOCKER_BUILDKIT=1

project_root=$(dirname "$(dirname "$(dirname "$(realpath "$0" )")")")

IMAGE_NAME="apm-agent-python-testing"
REGISTRY="elasticobservability"

while (( "$#" )); do
  case "$1" in
    -n|--name)
      IMAGE_NAME=$2
      shift 2
      ;;
    -r|--registry)
      REGISTRY=$2
      shift 2
      ;;
    -a|--action)
      ACTION=$2
      shift 2
      ;;
    --) # end argument parsing
      shift
      break
      ;;
    -*|--*=) # unsupported flags
      echo "Error: Unsupported flag $1" >&2
      exit 1
      ;;
    *) # preserve positional arguments
      shift
      ;;
  esac
done

versions=$(yq '.VERSION[]' "${project_root}/.ci/.matrix_python_full.yml")

for version in $versions; do

  full_image_name="${REGISTRY}/${IMAGE_NAME}:${version}"

  case $ACTION in
  build)
    docker build \
        --cache-from="${full_image_name}" \
        -f "${project_root}/tests/Dockerfile" \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --build-arg PYTHON_IMAGE="${version/-/:}" \
        -t "${full_image_name}" \
        "${project_root}/tests"
    ;;
  push)
    docker push "${full_image_name}"
    ;;
  esac
done
