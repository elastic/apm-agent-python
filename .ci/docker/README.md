# apm-agent-python docker images for testing

Utility script for building and pushing the images based on `.ci/.matrix_python_full.yml`.

> :information_source: This script is mainly used in [publish-docker-images](https://github.com/elastic/apm-agent-java/actions/workflows/build-images.yml) workflow,
which can be triggered safely at any time.

## Options

| Name     | Description                                               |
|----------|-----------------------------------------------------------|
| name     | Name of the docker image. (`<registry>/<name>:<tag>`)     |
| registry | Registry of the docker image. (`<registry>/<name>:<tag>`) |
| action   | Either `build` or `push`.                                 |

## Usage

### Build

To build the images run

```bash
  ./util.sh --action build
```

You can set your own docker registry with the flag `--registry x.y.z/org`. The default is `elasticobservability`.

### Push

To push the images run

```bash
  ./util.sh --action push
```
