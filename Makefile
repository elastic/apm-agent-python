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

check-licenses:
	@go get -u github.com/elastic/go-licenser
	@go-licenser -ext .py .

docker-check-licenses:
	docker run --rm -v "$$PWD":/usr/src -w /usr/src golang:1.12 make check-licenses

.PHONY: isort flake8 test coverage docs update-json-schema check-licenses
