#!/usr/bin/env bash
set -ex

function cleanup {
    PYTHON_VERSION=${1} REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} docker compose down -v

    if [[ $CODECOV_TOKEN ]]; then
        cd ..
        bash <(curl -s https://codecov.io/bash) -e PYTHON_VERSION,FRAMEWORK || true
    fi
}
trap cleanup EXIT

if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi

pip_cache="$HOME/.cache"
docker_pip_cache="/tmp/cache/pip"
TEST="${1}/${2}"
LOCAL_USER_ID=${LOCAL_USER_ID:=$(id -u)}
LOCAL_GROUP_ID=${LOCAL_GROUP_ID:=$(id -g)}
IMAGE_NAME=${IMAGE_NAME:-"apm-agent-python-testing"}
REGISTRY=${REGISTRY:-"elasticobservability"}

cd tests

# check if the full FRAMEWORK name is in scripts/envs

if [[ -e "./scripts/envs/${2}.sh" ]]
then
    source ./scripts/envs/${2}.sh
else
    # check if only the first part of the FRAMEWORK is in scripts/envs
    IFS='-'; frameworkParts=($2); unset IFS;
    if [[ -e "./scripts/envs/${frameworkParts[0]}.sh" ]]
    then
        source ./scripts/envs/${frameworkParts[0]}.sh
    fi
fi

echo "Running tests for ${TEST}"

if [[ -n $DOCKER_DEPS ]]
then
    PYTHON_VERSION=${1} REGISTRY=${REGISTRY} IMAGE_NAME=${IMAGE_NAME} docker compose up --quiet-pull -d ${DOCKER_DEPS}
fi

# CASS_DRIVER_NO_EXTENSIONS is set so we don't build the Cassandra C-extensions,
# as this can take several minutes

if ! ${CI}; then
  full_image_name="${REGISTRY}/${IMAGE_NAME}:${1}"
  DOCKER_BUILDKIT=1 docker build \
    --progress=plain \
    --cache-from="${full_image_name}" \
    --build-arg PYTHON_IMAGE="${1/-/:}" \
    --tag "${full_image_name}" \
    .
fi

PYTHON_VERSION=${1} docker compose run --quiet-pull \
  -e PYTHON_FULL_VERSION=${1} \
  -e LOCAL_USER_ID=$LOCAL_USER_ID \
  -e LOCAL_GROUP_ID=$LOCAL_GROUP_ID \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -e FRAMEWORK=${2} \
  -e PIP_CACHE=${docker_pip_cache} \
  -e WITH_COVERAGE=true \
  -e CASS_DRIVER_NO_EXTENSIONS=1 \
  -e PYTEST_JUNIT="--junitxml=/app/tests/docker-${1}-${2}-python-agent-junit.xml" \
  -e REGISTRY=${REGISTRY} \
  -e IMAGE_NAME=${IMAGE_NAME} \
  -v ${pip_cache}:$(dirname ${docker_pip_cache}) \
  -v "$(dirname $(pwd))":/app \
  --rm run_tests \
	/bin/bash \
  -c "timeout 5m /bin/bash ./tests/scripts/run_tests.sh"
