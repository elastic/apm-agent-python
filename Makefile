test:
	python setup.py test

coverage:
	coverage run runtests.py --include=opbeat/* && \
	coverage html --omit=*/migrations/* -d cover
