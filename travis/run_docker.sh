#!/usr/bin/env bash
if [ -z ${TRAVIS_TAG+x} ]; then
  echo "Not a tagged build, skipping building wheels";
else
  mkdir -p wheelhouse;
  docker run --rm -v `pwd`:/io $DOCKER_IMAGE $PRE_CMD /io/travis/build_manylinux_wheels.sh;
  ls wheelhouse/;
fi