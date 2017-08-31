#!/usr/bin/env bash

if [ $# -lt 1 ]; then
  echo "label missing"
  exit 2
fi

dockerps=$(docker ps -a -q --filter "label=$1")
if [ ! -z "$dockerps" ]; then
  docker stop $dockerps
  docker rm $dockerps
fi
