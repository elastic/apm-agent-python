#!/usr/bin/env bash
if [[ $# -eq 0 ]]
then
    FILES=$(find . -iname "*.py" -not -path "./elasticapm/utils/wrapt/*" -not -path "./dist/*" -not -path "./build/*" -not -path "./tests/utils/stacks/linenos.py")
else
    FILES=$@
fi

MISSING=$(grep --files-without-match "Copyright (c) [0-9]..., Elastic" ${FILES})

if [[ -z "$MISSING" ]]
then
    exit 0
else
    echo "Files with missing copyright header:"
    echo $MISSING
    exit 1
fi
