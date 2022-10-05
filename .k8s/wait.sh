#!/usr/bin/env bash

set -euo pipefail

countTestJobs() {
  kubectl get job.batch -o name -l repo=apm-agent-python,type=unit-test  2> /dev/null \
  | wc -l
}

echo ">> Waiting for test jobs to start [$(date)]"
jobcount=0
while [ $jobcount -eq 0 -o $jobcount -ne $(countTestJobs) ]; do
    jobcount=$(countTestJobs)
    sleep 5
done

echo ">> Monitoring for test job completion [$(date)]"
kubectl wait --for=condition=complete job.batch --timeout=120s \
    -l repo=apm-agent-python,type=unit-test 2> /dev/null

echo ">> Export logs TBC"
