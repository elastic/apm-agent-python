isort:
	isort -rc -vb .

test:
	if [ "$$TRAVIS_PYTHON_VERSION" != "3.5" ]; then \
	py.test --ignore=tests/asyncio; \
	else py.test; fi

coverage:
	coverage run runtests.py --include=elasticapm/* && \
	coverage html --omit=*/migrations/* -d cover

.PHONY: isort test coverage
