#!/usr/bin/env bash
set -exo pipefail

## Buildkite specific configuration
if [ "$CI" == "true" ] ; then
	# If HOME is not set then use the Buildkite workspace
	# that's normally happening when running in the CI
	# owned by Elastic.
	if [ -z "$HOME" ] ; then
		HOME=$BUILDKITE_BUILD_CHECKOUT_PATH
		export HOME
	fi

	# required when running the benchmark
	PATH=$PATH:$HOME/.local/bin
	export PATH
fi

## Bench specific
LANG='C.UTF-8'
LC_ALL="${LANG}"
export LANG
export LC_ALL

# APM_AGENT_PYTHON* env variables are provided by the Buildkite hooks.
./scripts/run-benchmarks.sh "$(pwd)" "${APM_AGENT_PYTHON_ES_URL_SECRET}" "${APM_AGENT_PYTHON_ES_USER_SECRET}" "${APM_AGENT_PYTHON_ES_PASS_SECRET}"
