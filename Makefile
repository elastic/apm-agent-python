BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort -rc -vb .

flake8:
	flake8

test:
	if [[ "$$PYTHON_VERSION" =~ ^(3.6|3.7|3.8|nightly|pypy3)$$ ]] ; then \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT); \
	elif [[ "$$PYTHON_VERSION" =~ ^3\.5$$ ]] ; then \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore-glob='*/asyncio/*'; \
	else \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore-glob='*/py3_*.py' --ignore-glob='*/asyncio/*'; \
	fi

coverage: PYTEST_ARGS=--cov --cov-context=test --cov-config=setup.cfg --cov-branch
coverage: export COVERAGE_FILE=.coverage.$(PYTHON_FULL_VERSION).$(WEBFRAMEWORK)
coverage: test

docs:
	bash ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

update-json-schema:
	bash ./tests/scripts/download_json_schema.sh

.PHONY: isort flake8 test coverage docs update-json-schema
