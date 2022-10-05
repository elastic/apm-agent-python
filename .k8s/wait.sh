#!/usr/bin/env bash
set -euo pipefail

##########################
### Variables
##########################

BATCH_FILTER="-l repo=apm-agent-python,type=unit-test,user.repo=${GIT_USERNAME}"
NAMESPACE="--namespace ${K8S_NAMESPACE}"

##########################
### Functions
##########################
function countTestJobs {
  kubectl get job.batch -o name $BATCH_FILTER $NAMESPACE 2> /dev/null \
  | wc -l
}

function finish {
    echo ">> Export logs"
    mkdir -p ../build
    POD=$(kubectl get job.batch -o name $BATCH_FILTER $NAMESPACE)
    for CONTAINER in $(kubectl get job.batch $BATCH_FILTER $NAMESPACE -o jsonpath="{.items[*].spec.template.spec.containers[*].name}")
    do
        echo ">>> Container $CONTAINER"
        kubectl logs $POD --container $CONTAINER $NAMESPACE > ..build/$CONTAINER.out
    done
}
trap finish SIGINT SIGTERM ERR EXIT

function waitForJobsToStart {
    jobcount=0
    while [ $jobcount -eq 0 -o $jobcount -ne $(countTestJobs) ]; do
        jobcount=$(countTestJobs)
        sleep 5
    done
}

function waitForCompletion {
    kubectl wait \
        job.batch \
        --for=condition=complete \
        --timeout=600s \
        $BATCH_FILTER $NAMESPACE 2> /dev/null
}

##########################
### Main
##########################

echo ">> Waiting for test jobs to start [$(date)]"
waitForJobsToStart

echo ">> Monitoring for test job completion [$(date)]"
waitForCompletion
