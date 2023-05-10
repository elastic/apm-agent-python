#!/usr/bin/env bash
set -exo pipefail

## Buildkite specific configuration
if [ "$CI" == "true" ] ; then
	# If HOME is not set then use the current directory
	# that's normally happening when running in the CI
	# owned by Elastic.
	if [ -z "$HOME" ] ; then
		HOME=$(realpath ~)
		export HOME
	fi

	# Consumed in scripts/run-benchmarks.sh
	BRANCH_NAME=${GITHUB_REF##*/}
	export BRANCH_NAME
fi

## Bench specific
LANG='C.UTF-8'
LC_ALL="${LANG}"
export LANG
export LC_ALL

./scripts/run-benchmarks.sh "$(realpath ~)" "${APM_AGENT_GO_ES_URL}" "${APM_AGENT_GO_ES_USER}" "${APM_AGENT_GO_ES_PASS}"
