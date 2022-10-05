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

## Skaffold

```bash
$ make -C .k8s skaffold-build skaffold-test
```

### Use case

When things go very well

```bash
$ make -C .k8s skaffold-test
Tags used in deployment:
 - apm-agent-python-3.6 -> docker.elastic.co/beats-dev/apm-agent-python-3_6:v6.12.0-33-gb6cfe0d3-dirty@sha256:4b5557bead9abb6e590cd8240dc0f2fb25165a1214e757d510f1e3bcfc1a1f83
 - apm-agent-python-3.7 -> docker.elastic.co/beats-dev/apm-agent-python-3_7:v6.12.0-33-gb6cfe0d3-dirty@sha256:b8bc4fb1fcbc1da921d3aaa9a2634e1c9017d309006533258f814fb93ba21e63
 - apm-agent-python-3.8 -> docker.elastic.co/beats-dev/apm-agent-python-3_8:v6.12.0-33-gb6cfe0d3-dirty@sha256:11b64ce873b1663ca80e363a962c3cbf2fe9f9cdaccfdf268ab2ff84cf3f9a7a
 - apm-agent-python-3.9 -> docker.elastic.co/beats-dev/apm-agent-python-3_9:v6.12.0-33-gb6cfe0d3-dirty@sha256:f70a02c2cfffb776f07c62c823c09454f136de81c3beb61a6c49fa1d4d58a616
 - apm-agent-python-3.10 -> docker.elastic.co/beats-dev/apm-agent-python-3_10:v6.12.0-33-gb6cfe0d3-dirty@sha256:24f20916f2f24f233d2c978018121272b2d963a9231ef83cafe5293da21ace27
Starting deploy...
 - job.batch/python-versions-pod created
Waiting for deployments to stabilize...
Deployments stabilized in 1.027 second

>> Waiting for test jobs to start [Wed  5 Oct 2022 22:07:39 BST]
.    Started
>> Monitoring for test job completion [Wed  5 Oct 2022 22:07:45 BST]
.............    Job completed
>> Export logs
    Logs for the container python-3-6 can be found in ../build/python-3-6.out
    Logs for the container python-3-7 can be found in ../build/python-3-7.out
    Logs for the container python-3-8 can be found in ../build/python-3-8.out
    Logs for the container python-3-9 can be found in ../build/python-3-9.out
    Logs for the container python-3-10 can be found in ../build/python-3-10.out
    Exported
$ echo $?
0
```
