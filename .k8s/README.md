# K8s

This folder contains all the definitions regarding the different python versions used for
testing the APM Agent Python with

## Pre-requisites

TBC

Access to a Kubernetes cluster, then configure the environment variables

```bash

```

## Use cases

### `unit-test` in all the defined pods

```bash
$ VAULT_TOKEN=$(cat ${HOME}/.vault-token) \
    make -C .k8s unit-test
$ VAULT_TOKEN=$(cat ${HOME}/.vault-token) \
    make -C .k8s report-unit-test-results
```

### Know what you can do with the existing make

```bash
$ make -C .k8s help
```

