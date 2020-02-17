#!/usr/bin/env bash
set -euo pipefail

DOCKER_IDS=$(docker ps -aq)

for id in ${DOCKER_IDS}
do
  echo "***********************************************************"
  echo "***************Docker Container ${id}***************"
  echo "***********************************************************"
  docker ps -af id=${id} --no-trunc
  echo "----"
  docker logs ${id} | tail -n 10 || echo "It is not possible to grab the logs of ${id}"
done

echo "*******************************************************"
echo "***************Docker Containers Summary***************"
echo "*******************************************************"
docker ps -a
