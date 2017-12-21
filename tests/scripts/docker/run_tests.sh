#!/usr/bin/env bash
set -e

if [ $# -lt 2 ]; then
  echo "Arguments missing"
  exit 2
fi

pip_cache="$HOME/.cache"
docker_pip_cache="/tmp/cache/pip"

cd tests

docker-compose build --pull --build-arg PYTHON_IMAGE=${1/-/:} run_tests # replace - with : to get the correct docker image
docker-compose run \
  -e LOCAL_USER_ID=$UID \
  -e PYTHONDONTWRITEBYTECODE=1 -e WEBFRAMEWORK=$2 -e PIP_CACHE=${docker_pip_cache} \
  -e WITH_COVERAGE=true \
  -v ${pip_cache}:$(dirname ${docker_pip_cache}) \
  -v "$(dirname $(pwd))":/app \
  --rm run_tests \
	/bin/bash \
  -c "./tests/scripts/run_tests.sh"

cd ..

if [[ $CODECOV_TOKEN ]]; then
    bash <(curl -s https://codecov.io/bash) -e PYTHON_VERSION,WEBFRAMEWORK
fi
