BUILD_DIR?=build
SHELL := /bin/bash

isort:
	isort --vb .

flake8:
	flake8

test:
	# delete any __pycache__ folders to avoid hard-to-debug caching issues
	find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
	echo "Python 3.7+, with asyncio"; \
	pytest -v $(PYTEST_ARGS) --showlocals $(PYTEST_MARKER) $(PYTEST_JUNIT); \

coverage: PYTEST_ARGS=--cov --cov-context=test --cov-config=setup.cfg --cov-branch
coverage: export COVERAGE_FILE=.coverage.docker.$(PYTHON_FULL_VERSION).$(FRAMEWORK)
coverage: test

docs:
	bash ./scripts/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

.PHONY: isort flake8 test coverage docs
