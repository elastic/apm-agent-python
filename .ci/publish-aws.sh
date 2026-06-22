#!/usr/bin/env bash
set -euo pipefail

#
# Publishes the created artifacts from ./dev-utils/make-distribution.sh to AWS as AWS Lambda Layers in every region.
# Finalized by generating an ARN table which will be used in the release notes.
#
# AWS_FOLDER is used for temporary output of publishing layers used to create the arn table. (Optional)
# ELASTIC_LAYER_NAME is the name of the lambda layer e.g. elastic-apm-python-ver-3-44-1 for the git tag v3.44.1 (Required)


# This needs to be set in GH actions
# https://dotjoeblog.wordpress.com/2021/03/14/github-actions-aws-error-exit-code-255/
# eu-west-1 is just a random region
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-eu-west-1}

export AWS_FOLDER=${AWS_FOLDER:-.aws}
FULL_LAYER_NAME=${ELASTIC_LAYER_NAME:?layer name not provided}
ALL_AWS_REGIONS=$(aws ec2 describe-regions --output json --no-cli-pager | jq -r '.Regions[].RegionName')

rm -rf "${AWS_FOLDER}"
mkdir -p "${AWS_FOLDER}"

failed_regions=()

# Delete previous layers
for region in $ALL_AWS_REGIONS; do
  layer_versions=$(aws --cli-connect-timeout 30 lambda list-layer-versions --region="${region}" --layer-name="${ELASTIC_LAYER_NAME}" | jq '.LayerVersions[].Version') || {
    echo "WARNING: Could not list layer versions in ${region}, skipping deletion"
    continue
  }
  echo "Found layer versions for ${FULL_LAYER_NAME} in ${region}: ${layer_versions:-none}"
  for version_number in $layer_versions; do
    echo "- Deleting ${FULL_LAYER_NAME}:${version_number} in ${region}"
    aws --cli-connect-timeout 30 lambda delete-layer-version \
        --region="${region}" \
        --layer-name="${FULL_LAYER_NAME}" \
        --version-number="${version_number}"
  done
done


zip_file="./build/dist/elastic-apm-python-lambda-layer.zip"

for region in $ALL_AWS_REGIONS; do
  echo "Publish ${FULL_LAYER_NAME} in ${region}"
  if ! publish_output=$(aws --cli-connect-timeout 30 lambda \
    --output json \
    publish-layer-version \
    --region="${region}" \
    --layer-name="${FULL_LAYER_NAME}" \
    --description="AWS Lambda Extension Layer for the Elastic APM Python Agent" \
    --license-info="BSD-3-Clause" \
    --compatible-runtimes python3.6 python3.7 python3.8 python3.9 python3.10 python3.11 python3.12 python3.13 python3.14\
    --zip-file="fileb://${zip_file}"); then
    echo "WARNING: Failed to publish to ${region}"
    failed_regions+=("${region}")
    continue
  fi
  echo "${publish_output}" > "${AWS_FOLDER}/${region}"
  layer_version=$(echo "${publish_output}" | jq '.Version')
  echo "Grant public layer access ${FULL_LAYER_NAME}:${layer_version} in ${region}"
  if ! grant_access_output=$(aws --cli-connect-timeout 30 lambda \
  		--output json \
  		add-layer-version-permission \
  		--region="${region}" \
  		--layer-name="${FULL_LAYER_NAME}" \
  		--action="lambda:GetLayerVersion" \
  		--principal='*' \
  		--statement-id="${FULL_LAYER_NAME}" \
  		--version-number="${layer_version}"); then
    echo "WARNING: Failed to grant public access in ${region}"
    failed_regions+=("${region}")
    continue
  fi
  echo "${grant_access_output}" > "${AWS_FOLDER}/.${region}-public"
done

sh -c "./.ci/create-arn-table.sh"

if [ ${#failed_regions[@]} -gt 0 ]; then
  echo "WARNING: Failed to publish to the following regions: ${failed_regions[*]}"
  echo "WARNING: The layer is not available in those regions. Please publish manually or investigate connectivity."
fi
