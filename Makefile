BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort --vb .

flake8:
	flake8

test:
    # delete any __pycache__ folders to avoid hard-to-debug caching issues
    find . -name __pycache__ -type d -exec rm -r {} +
	# pypy3 should be added to the first `if` once it supports py3.7
	if [[ "$$PYTHON_VERSION" =~ ^(3.7|3.8|3.9|nightly)$$ ]] ; then \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT); \
	elif [[ "$$PYTHON_VERSION" =~ ^(3.5|3.6|pypy3)$$ ]] ; then \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore-glob='*/asyncio*/*'; \
	else \
		py.test -v $(PYTEST_ARGS) $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore-glob='*/py3_*.py' --ignore-glob='*/asyncio*/*'; \
	fi

coverage: PYTEST_ARGS=--cov --cov-context=test --cov-config=setup.cfg --cov-branch
coverage: export COVERAGE_FILE=.coverage.$(PYTHON_FULL_VERSION).$(WEBFRAMEWORK)
coverage: test

docs:
	bash ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

.PHONY: isort flake8 test coverage docs
