#!/usr/bin/env bash

USER_ID=${LOCAL_USER_ID:-1001}

echo "Starting with UID: $USER_ID"
useradd --shell /bin/bash -u $USER_ID --gid 0 --non-unique --comment "" --create-home user
export HOME=/home/user

exec /usr/local/bin/gosu user "$@"
