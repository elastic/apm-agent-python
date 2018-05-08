#!/usr/bin/env bash

set -x

# parent directory
basedir=$(dirname "$0")/..

FILES=( \
    "errors/error.json" \
    "errors/payload.json" \
    "sourcemaps/payload.json" \
    "transactions/mark.json" \
    "transactions/payload.json" \
    "transactions/span.json" \
    "transactions/transaction.json" \
    "context.json" \
    "process.json" \
    "request.json" \
    "service.json" \
    "stacktrace_frame.json" \
    "system.json" \
    "user.json" \
)

mkdir -p ${basedir}/.schemacache/errors ${basedir}/.schemacache/transactions ${basedir}/.schemacache/sourcemaps

for i in "${FILES[@]}"; do
    output="${basedir}/.schemacache/${i}"
    curl -s https://raw.githubusercontent.com/elastic/apm-server/master/docs/spec/${i} --compressed > ${output}
done
echo "Done."
