#!/usr/bin/env bash
if [[ $# -eq 0 ]]
  then
    FILES=$(find . -iname "*.py" -not -path "./elasticapm/utils/wrapt/*" -not -path "./dist/*" -not -path "./build/*" -not -path "./tests/utils/stacks/linenos.py")
else
    FILES=$@
fi

echo ${FILES} | xargs -n 1 grep --files-without-match "Copyright (c) [0-9]..., Elastic"
