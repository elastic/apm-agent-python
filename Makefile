isort:
	isort -rc -vb .

test:
	if [ "$$TRAVIS_PYTHON_VERSION" != "3.5" ]; then \
	py.test --isort --ignore=tests/asyncio; \
	else py.test --isort; fi

coverage:
	coverage run runtests.py --include=opbeat/* && \
	coverage html --omit=*/migrations/* -d cover

.PHONY: isort test coverage
