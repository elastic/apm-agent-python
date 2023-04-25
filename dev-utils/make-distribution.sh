#!/bin/bash
#
# Make a Python APM agent distribution that is used as follows:
# - "build/dist/elastic-apm-python-lambda-layer.zip" is published to AWS as a
#   Lambda layer (https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
# - "build/dist/package/python/..." is used to build a Docker image of the APM agent
#

if [ "$TRACE" != "" ]; then
    export PS4='${BASH_SOURCE}:${LINENO}: ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
    set -o xtrace
fi
set -o errexit
set -o pipefail

# ---- support functions

function fatal {
    echo "$(basename $0): error: $*"
    exit 1
}

# ---- mainline

TOP=$(cd $(dirname $0)/../ >/dev/null; pwd)
BUILD_DIR="$TOP/build/dist"

if ! command -v pip >/dev/null 2>&1; then
    fatal "pip is unavailable"
fi

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

rm -f elastic-apm-python-lambda-layer.zip
rm -f requirements.txt
rm -rf package
mkdir package
cp "$TOP/dev-utils/requirements.txt" .
echo "$TOP" >> ./requirements.txt
pip install -r requirements.txt --target ./package/python
cd package
cp python/elasticapm/contrib/serverless/aws_wrapper/elasticapm-run.py ./elasticapm-run
chmod +x ./elasticapm-run
cp python/elasticapm/contrib/serverless/aws_wrapper/elasticapm_handler.py ./python/
cp "$TOP/elasticapm/contrib/serverless/aws_wrapper/NOTICE.md" ./python/

echo ""
zip -q -r ../elastic-apm-python-lambda-layer.zip .
echo "Created build/dist/elastic-apm-python-lambda-layer.zip"

cd ..


echo
echo "The lambda layer can be published as follows for dev work:"
echo "    aws lambda --output json publish-layer-version --layer-name '$USER-dev-elastic-apm-python' --description '$USER dev Elastic APM Python agent lambda layer' --zip-file 'fileb://build/dist/elastic-apm-python-lambda-layer.zip'"
