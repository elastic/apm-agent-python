#!/usr/bin/env bash

set -x

# parent directory
basedir=$(dirname "$0")/..

FILES=( \
	"context.json" \
	"errors/error.json" \
	"errors/payload.json" \
	"meta.json" \
	"process.json" \
	"request.json" \
	"schema.json" \
	"service.json" \
	"sourcemaps/payload.json" \
	"stacktrace_frame.json" \
	"system.json" \
	"transactions/mark.json" \
	"transactions/payload.json" \
	"transactions/span.json" \
	"transactions/transaction.json" \
	"user.json" \
)

mkdir -p ${basedir}/.schemacache/errors ${basedir}/.schemacache/transactions ${basedir}/.schemacache/sourcemaps

for i in "${FILES[@]}"; do
    output="${basedir}/.schemacache/${i}"
    curl -s https://raw.githubusercontent.com/elastic/apm-server/master/docs/spec/${i} --compressed > ${output}
done
echo "Done."
