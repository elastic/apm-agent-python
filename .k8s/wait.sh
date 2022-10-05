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
    for POD in $(kubectl get job.batch -o name $BATCH_FILTER $NAMESPACE)
    do
        POD_NAME=$(basename $POD)
        mkdir -p $BUILD_OUTPUT_DIR/$POD_NAME
        for CONTAINER in $(kubectl get job.batch --field-selector metadata.name=$POD_NAME $BATCH_FILTER $NAMESPACE -o jsonpath="{.items[*].spec.template.spec.containers[*].name}")
        do
            echo -e "    ${BLUE}Logs for the container $POD_NAME:$CONTAINER can be found in $BUILD_OUTPUT_DIR/$POD_NAME/$CONTAINER.out${NC}"
            kubectl logs $POD --container $CONTAINER $NAMESPACE > $BUILD_OUTPUT_DIR/$POD_NAME/$CONTAINER.out
            #echo -e "    ${BLUE}JUnit for the container $CONTAINER can be found in $BUILD_OUTPUT_DIR/$CONTAINER-junit.xml${NC}"
            #echo "kubectl cp --container $CONTAINER $NAMESPACE $POD:/code/tests/python-agent-junit.xml $BUILD_OUTPUT_DIR/$CONTAINER-junit.xml"
        done
    done
    echo -e "    ${GREEN}Exported${NC}"
}
trap finish ERR EXIT

function waitForJobsToStart {
    jobcount=0
    while [ $jobcount -eq 0 -o $jobcount -ne $(countTestJobs) ]; do
        echo -n "."
        jobcount=$(countTestJobs)
        sleep 5
    done
    echo -e "    ${GREEN}Started${NC}"
}

# See https://stackoverflow.com/questions/55073453/wait-for-kubernetes-job-to-complete-on-either-failure-success-using-command-line
function waitForCompletion {
    while true; do
        echo -n "."
        if kubectl wait job.batch --for=condition=complete --timeout=0 $BATCH_FILTER $NAMESPACE &>/dev/null; then
            job_result=0
            break
        fi

        if kubectl wait job.batch --for=condition=failed --timeout=0 $BATCH_FILTER $NAMESPACE &>/dev/null; then
            job_result=1
            break
        fi

        sleep 5
    done

    if [[ $job_result -eq 0 ]]; then
        echo -e "    ${GREEN}Job completed${NC}"
    else
        echo -e "    ${RED}Job failed with exit code ${job_result}, ${NC}exiting..."
        exit $job_result
    fi
}

##########################
### Main
##########################

echo ">> Waiting for test jobs to start [$(date)]"
waitForJobsToStart

echo ">> Monitoring for test job completion [$(date)]"
waitForCompletion
