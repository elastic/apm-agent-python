#!/usr/bin/env bash

set -x

download_schema()
{
    from=$1
    to=$2

    for run in {1..5}
    do
        curl -sf --compressed ${from} > ${to}
        result=$?
        if [ $result -eq 0 ]; then break; fi
        sleep 1
    done

    if [ $result -ne 0 ]; then exit $result; fi
}

# parent directory
basedir=$(dirname "$0")/..
branch="v2"

FILES=( \
    "errors/common_error.json" \
    "errors/v1_error.json" \
    "errors/v2_error.json" \
    "sourcemaps/payload.json" \
    "metricsets/payload.json" \
    "metricsets/sample.json" \
    "metricsets/common_metricset.json" \
    "metricsets/v1_metricset.json" \
    "metricsets/v2_metricset.json" \
    "spans/common_span.json" \
    "spans/v1_span.json" \
    "spans/v2_span.json" \
    "transactions/common_transaction.json" \
    "transactions/mark.json" \
    "transactions/v1_transaction.json" \
    "transactions/v2_transaction.json" \
    "context.json" \
    "metadata.json" \
    "process.json" \
    "request.json" \
    "service.json" \
    "stacktrace_frame.json" \
    "system.json" \
    "tags.json" \
    "user.json" \
)

mkdir -p ${basedir}/.schemacache/errors ${basedir}/.schemacache/transactions ${basedir}/.schemacache/spans ${basedir}/.schemacache/metricsets ${basedir}/.schemacache/sourcemaps

for i in "${FILES[@]}"; do
    download_schema https://raw.githubusercontent.com/elastic/apm-server/${branch}/docs/spec/${i} ${basedir}/.schemacache/${i}
done
echo "Done."
