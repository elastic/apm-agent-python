BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort -rc -vb .

flake8:
	flake8

test:
	if [[ "$$PYTHON_VERSION" =~ ^(3.5|3.6|nightly|pypy3)$$ ]] ; then \
	py.test -v $(PYTEST_ARGS); \
	else py.test -v $(PYTEST_ARGS) --ignore=tests/asyncio; fi

coverage: PYTEST_ARGS=--cov --cov-report xml:coverage.xml
coverage: test

docs:
	sh ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

.PHONY: isort flake8 test coverage docs
