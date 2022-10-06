ARG PYTHON_VERSION
FROM docker.elastic.co/beats-dev/apm-agent-python:${PYTHON_VERSION}
ENV WEBFRAMEWORK=none
ENV PYTHONDONTWRITEBYTECODE=1
ENV CASS_DRIVER_NO_EXTENSIONS=1
ENV PYTEST_JUNIT="--junitxml=/tmp/python-agent-junit.xml"
WORKDIR /code
ADD . .
