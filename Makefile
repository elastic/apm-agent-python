test:
#	pep8 --exclude=migrations --ignore=E501,E225,E121,E123,E124,E125,E127,E128 opbeat_python || exit 1
	pyflakes -x W opbeat_python || exit 1
	python setup.py test

coverage:
	coverage run runtests.py --include=opbeat_python/* && \
	coverage html --omit=*/migrations/* -d cover
