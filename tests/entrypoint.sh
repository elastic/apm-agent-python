#!/usr/bin/env bash

USER_ID=${LOCAL_USER_ID:-1001}
GROUP_ID=${LOCAL_GROUP_ID:-1001}

echo "Starting with UID: ${USER_ID} and GID: ${GROUP_ID}"
groupadd -g "${GROUP_ID}" user
useradd --shell /bin/bash -u "${USER_ID}" --gid $GROUP_ID --non-unique --comment "" --create-home user
export HOME=/home/user

exec /usr/local/bin/gosu $USER_ID:$GROUP_ID "$@"
