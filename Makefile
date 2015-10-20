isort:
	isort -rc -vb .

test:
	py.test --isort

coverage:
	coverage run runtests.py --include=opbeat/* && \
	coverage html --omit=*/migrations/* -d cover

.PHONY: isort test coverage