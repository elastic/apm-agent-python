#!/usr/bin/env bash

DOCKER_IDS=$(docker ps -a -q) 

if [ -n "${DOCKER_IDS}" ]; then
  docker stop ${DOCKER_IDS}
  docker rm -v ${DOCKER_IDS}
  docker volume prune -f
fi

exit 0
