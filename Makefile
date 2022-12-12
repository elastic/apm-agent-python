BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort --vb .

flake8:
	flake8

test:
	# delete any __pycache__ folders to avoid hard-to-debug caching issues
	find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
	# pypy3 should be added to the first `if` once it supports py3.7
	if [[ "$$PYTHON_VERSION" =~ ^(3.7|3.8|3.9|3.10|3.11|nightly)$$ ]] ; then \
		echo "Python 3.7+, with asyncio"; \
		py.test -v $(PYTEST_ARGS) --showlocals $(PYTEST_MARKER) $(PYTEST_JUNIT); \
	else \
		echo "Python < 3.7, without asyncio"; \
		py.test -v $(PYTEST_ARGS) --showlocals $(PYTEST_MARKER) $(PYTEST_JUNIT) --ignore-glob='*/asyncio*/*'; \
	fi

coverage: PYTEST_ARGS=--cov --cov-context=test --cov-config=setup.cfg --cov-branch
coverage: export COVERAGE_FILE=.coverage.$(PYTHON_FULL_VERSION).$(WEBFRAMEWORK)
coverage: test

docs:
	bash ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

.PHONY: isort flake8 test coverage docs
