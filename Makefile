BUILD_DIR?=build

isort:
	isort -rc -vb .

flake8:
	flake8 elasticapm

test:
	if [ "$$TRAVIS_PYTHON_VERSION" != "3.5" ]; then \
	py.test --ignore=tests/asyncio; \
	else py.test; fi

coverage:
	coverage run runtests.py --include=elasticapm/* && \
	coverage html --omit=*/migrations/* -d cover

docs:
	sh ./script/build_docs.sh apm-agent-python ./docs ${BUILD_DIR}

.PHONY: isort flake8 test coverage docs
