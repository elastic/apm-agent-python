BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort -rc -vb .

flake8:
	flake8

test:
	if [[ "$$PYTHON_VERSION" =~ ^(3.5|3.6|nightly|pypy3)$$ ]] ; then \
	py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT); \
	else py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore=tests/asyncio; fi

coverage: PYTEST_ARGS=--cov --cov-report xml:coverage.xml
coverage: test

docs:
	bash ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

update-json-schema:
	bash ./tests/scripts/download_json_schema.sh

.PHONY: isort flake8 test coverage docs update-json-schema
