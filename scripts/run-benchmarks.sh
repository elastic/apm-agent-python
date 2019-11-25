#!/usr/bin/env bash
set -ex

COMMIT_SHA=${1:?Please specify the git SHA commit}
ES_URL=${2:?Please specify the elasticstack URL}
ES_USER=${3:?Please specify the user to connect with}
ES_PASS=${4:?Please specify the password to connect with}

git clone https://github.com/elastic/apm-agent-python-benchmarks.git .benchmarks

cd .benchmarks

## Prepare virtualenv
virtualenv -p python3 "${HOME}/.local"

pip install --user -r requirements.txt

python run_bench_commits.py \
    --worktree agent \
    --es-url "${ES_URL}" \
    --es-user "${ES_USER}" \
    --es-password "${ES_PASS}" \
    --start-commit "${COMMIT_SHA}"
