# K8s

This folder contains all the definitions regarding the different python versions used for
testing the APM Agent Python with.

## Pre-requisites

* Access to the internal docker registry.
* Access to the Elastic Google Account.

##  Configuration

This is only required to configure your local environment with access to
K8s, skaffold and configure the default k8s cluster.

```bash
$ export PATH=${PATH}:$(pwd)/.k8s/bin
$ make -C .k8s k8s-login K8S_NAMESPACE=default
$ make -C .k8s skaffold-docker-base
```

## Versions

The list of supported versions can be found in:

* `.ci/.jenkins_framework.yml`
* `.ci/.jenkins_python.yml`

## Use cases

```bash
$ python3 .k8s/cli.py --help
```
### Generate the skaffold configuration files


```bash
## Generate the skaffold files
$ python3 .k8s/cli.py generate

## help for the generate command
$ python3 .k8s/cli.py generate --help

```

### Test any given framework

```bash
## Build all the docker images
$ python3 .k8s/cli.py build

## Build all the docker images for python-3.9 and python-3.10
$ python3 .k8s/cli.py build --version python-3.9 --version python-3.10

## Test django
$ python3 .k8s/cli.py test --framework django

## Test django-1.1 in python-3.6
$ python3 .k8s/cli.py test --framework django-1.1 --version python-3.6
```

Then the logs can be found under the `build/` folder.

## Implementation details

The list of frameworks and when they run can be found in `.ci`:

* `.ci/.jenkins_framework.yml`, when `FULL=false` or by default for any Pull Request.
* `.ci/.jenkins_framework_full.yml`, when `FULL=true` or by default for any merge commit.

The list fo supported python versions can be found in `.ci`:

* `.ci/.jenkins_python.yml`, when `FULL=false` or by default for any Pull Request.
* `.ci/.jenkins_python_full.yml`, when `FULL=true` or by default for any merge commit.


Then the K8s tasks to be executed are dynamically generated in `.k8s/generated`, and there will be
one file per `cell` in the Version/Framework matrix, with the naming convention: `<version>-<framework>.yaml`, i.e: `3.9-flask-0.10.yaml`

There will be only one container per pod, this will help to distribute the load in the K8s cluster. Additionally, it will simplify the implementation in the wait for the tasks to be finished.


## Further details

Current implementation runs the tests for those frameworks which are not dependent of any other services. See `.ci/.jenkins_framework_dependencies.yml` which provides
the list of frameworks with some dependencies.

In a follow up, we will implement the support for running pods with sevaral containers.

