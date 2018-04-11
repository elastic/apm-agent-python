#!/usr/bin/env bash
set -ex

if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi

pip_cache="$HOME/.cache"
docker_pip_cache="/tmp/cache/pip"

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

echo "Running tests for ${1}/${2}"

if [[ -n $DOCKER_DEPS ]]
then
    PYTHON_VERSION=${1} docker-compose up -d ${DOCKER_DEPS}
fi

docker build --pull --force-rm --build-arg PYTHON_IMAGE=${1/-/:} -t apm-agent-python:${1} . # replace - with : to get the correct docker image
PYTHON_VERSION=${1} docker-compose run \
  -e LOCAL_USER_ID=$UID \
  -e PYTHONDONTWRITEBYTECODE=1 -e WEBFRAMEWORK=$2 -e PIP_CACHE=${docker_pip_cache} \
  -e WITH_COVERAGE=true \
  -v ${pip_cache}:$(dirname ${docker_pip_cache}) \
  -v "$(dirname $(pwd))":/app \
  --rm run_tests \
	/bin/bash \
  -c "timeout 5m ./tests/scripts/run_tests.sh"

PYTHON_VERSION=${1} docker-compose down -v
cd ..

if [[ $CODECOV_TOKEN ]]; then
    bash <(curl -s https://codecov.io/bash) -e PYTHON_VERSION,WEBFRAMEWORK
fi
