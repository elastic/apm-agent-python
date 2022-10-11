# K8s

This folder contains all the definitions regarding the different python versions used for
testing the APM Agent Python with.

## Pre-requisites

TBC

Access to a Kubernetes cluster, then configure the environment variables

```bash

```

## Versions

The list of supported versions can be found in:

* `.ci/.jenkins_framework.yml`
* `.ci/.jenkins_python.yml`

## Use cases

### Generate the skaffold configuration

```bash
$ make -C .k8s skaffold-generate
```

### Syncup your local changes in a docker image

> :warning: This can expose some secrest, so be careful!

```bash
## For the default versions
$ make -C .k8s skaffold-build

## For all the python versions
$ FULL=true make -C .k8s skaffold-build
```

### Know what you can do with the existing make

```bash
$ make -C .k8s help
```

## Skaffold

```bash
$ make -C .k8s skaffold-build skaffold-test
```

### Test any given framework

```bash
## Build all the docker images
$ python3 .k8s/cli.py build

## Build all the docker images for python-3.9 and python-3.10
$ python3 .k8s/cli.py build --version python-3.9 --version python-3.10

## Test django
$ make -C .k8s skaffold-test-django

## Test django-1.1
$ make -C .k8s skaffold-test-django-1.1
```

## Implementation details

The list of frameworks and when they run can be found in `.ci`:

* `.ci/.jenkins_framework.yml`, when `FULL=false` or by default for any Pull Request.
* `.ci/.jenkins_framework_full.yml`, when `FULL=true` or by default for any merge commit.

The list fo supported python versions can be found in `.ci`:

* `.ci/.jenkins_python.yml`, when `FULL=false` or by default for any Pull Request.
* `.ci/.jenkins_python_full.yml`, when `FULL=true` or by default for any merge commit.

**NOTE**: Though those versions are also explicitly defined in `skaffold`. Potentially to remove the above and use the skaffold approach instead. TBR

Then the K8s tasks to be executed are dynamically generated in `.k8s/generated`, and there will be
one file per `cell` in the Version/Framework matrix, with the naming convention: `<version>-<framework>.yaml`, i.e: `3.9-flask-0.10.yaml`

There will be only one container per pod, this will help to distribute the load in the K8s cluster. Additionally, it will simplify the implementation in the wait for the tasks to be finished.


