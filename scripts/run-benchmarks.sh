#!/usr/bin/env bash
set -ex

AGENT_WORKDIR=${1:?Please specify the python agent workspace}
ES_URL=${2:?Please specify the elasticstack URL}
ES_USER=${3:?Please specify the user to connect with}
ES_PASS=${4:?Please specify the password to connect with}

## If BRANCH_NAME is set then use the tag filter.
## This particular env variable is inferred from the Jenkins CI.
EXTRA_ARGS=''
if [ -n "${BRANCH_NAME}" ] ; then
    EXTRA_ARGS="--tag \"branch=${BRANCH_NAME}\""
fi

if [ -d .benchmarks ] ; then
    rm -rf .benchmarks
fi
git clone https://github.com/elastic/apm-agent-python-benchmarks.git .benchmarks

cd .benchmarks

## Prepare virtualenv
virtualenv -p python3 "${HOME}/.local"

pip install -r requirements.txt

python run_bench_commits.py \
    --worktree "${AGENT_WORKDIR}" \
    --es-url "${ES_URL}" \
    --es-user "${ES_USER}" \
    --es-password "${ES_PASS}" \
    --as-is \
    "${EXTRA_ARGS}"
