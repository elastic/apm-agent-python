ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION}

WORKDIR /app

ENV PIP_CACHE ""
CMD ./tests/scripts/run_tests.sh
