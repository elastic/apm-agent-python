# Pin to Alpine 3.17.3
FROM alpine@sha256:a8560b36e8b8210634f77d9f7f9efd7ffa463e380b75e2e74aff4511df3ef88c
ARG AGENT_DIR
COPY ${AGENT_DIR} /opt/python