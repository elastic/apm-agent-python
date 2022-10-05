#!/usr/bin/env bash
set -euo pipefail

##########################
### Variables
##########################

BUILD_OUTPUT_DIR="../build"
BATCH_FILTER="-l repo=apm-agent-python,type=unit-test,user.repo=${GIT_USERNAME}"
NAMESPACE="--namespace ${K8S_NAMESPACE}"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

##########################
### Functions
##########################
function countTestJobs {
  kubectl get job.batch -o name $BATCH_FILTER $NAMESPACE 2> /dev/null | wc -l
}

function finish {
    echo ">> Export logs"
    mkdir -p $BUILD_OUTPUT_DIR
    POD=$(kubectl get job.batch -o name $BATCH_FILTER $NAMESPACE)
    for CONTAINER in $(kubectl get job.batch $BATCH_FILTER $NAMESPACE -o jsonpath="{.items[*].spec.template.spec.containers[*].name}")
    do
        echo -e "    ${BLUE}Logs for the container $CONTAINER can be found in $BUILD_OUTPUT_DIR/$CONTAINER.out${NC}"
        kubectl logs $POD --container $CONTAINER $NAMESPACE > $BUILD_OUTPUT_DIR/$CONTAINER.out
    done
    echo -e "    ${GREEN}Exported${NC}"
}
trap finish SIGINT SIGTERM ERR EXIT

function waitForJobsToStart {
    jobcount=0
    while [ $jobcount -eq 0 -o $jobcount -ne $(countTestJobs) ]; do
        jobcount=$(countTestJobs)
        sleep 5
    done
    echo -e "    ${GREEN}Started${NC}"
}

# See https://stackoverflow.com/questions/55073453/wait-for-kubernetes-job-to-complete-on-either-failure-success-using-command-line
function waitForCompletion {
    TIMEOUT_FLAG="--timeout=600s"

    # wait for completion as background process - capture PID
    kubectl wait job.batch --for=condition=complete $TIMEOUT_FLAG $BATCH_FILTER $NAMESPACE &
    completion_pid=$!

    # wait for failure as background process - capture PID
    kubectl wait job.batch --for=condition=failed $TIMEOUT_FLAG $BATCH_FILTER $NAMESPACE && exit 1 &
    failure_pid=$!

    # capture exit code of the first subprocess to exit
    wait -n $completion_pid $failure_pid
    # store exit code in variable
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo -e "    ${GREEN}Job completed${NC}"
    else
        echo -e "    ${RED}Job failed with exit code ${exit_code}, ${NC}exiting..."
    fi
    exit $exit_code
}

##########################
### Main
##########################

echo ">> Waiting for test jobs to start [$(date)]"
waitForJobsToStart

echo ">> Monitoring for test job completion [$(date)]"
waitForCompletion
