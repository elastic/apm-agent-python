#!/usr/bin/env python
"""
opbeat
======

opbeat is a Python client for `Opbeat <https://opbeat.com/>`_. It provides
full out-of-the-box support for many of the popular frameworks, including
`Django <djangoproject.com>`_, `Flask <http://flask.pocoo.org/>`_, and `Pylons
<http://www.pylonsproject.org/>`_. opbeat also includes drop-in support for any
`WSGI <http://wsgi.readthedocs.org/>`_-compatible web application.
"""

# Hack to prevent stupid "TypeError: 'NoneType' object is not callable" error
# in multiprocessing/util.py _exit_function when running `python
# setup.py test` (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
for m in ('multiprocessing', 'billiard'):
    try:
        __import__(m)
    except ImportError:
        pass

import sys
import os

from setuptools import setup, find_packages
from opbeat.version import VERSION
from setuptools.command.test import test as TestCommand

tests_require = [
    'py==1.4.26',
    'pytest==2.6.4',
    'pytest-django==2.8.0',
    'pytest-capturelog==0.7',
    'blinker>=1.1',
    'celery',
    'Django>=1.2',
    'django-celery',
    'Flask>=0.8',
    'logbook',
    'mock',
    'pep8',
    'webob',
    'pytz'
]

if sys.version_info[0] == 2:
    tests_require += [
        'unittest2',
        'gevent',
        'zerorpc>=0.4.0',
    ]

install_requires = []

try:
    # For Python >= 2.6
    import json
except ImportError:
    install_requires.append("simplejson>=2.3.0,<2.5.0")


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)


setup(
    name='opbeat',
    version=VERSION,
    author='Ron Cohen',
    author_email='ron@opbeat.com',
    url='https://github.com/opbeat/opbeat_python',
    description='The official Python module for Opbeat.com',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
    packages=find_packages(exclude=("tests",)),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'tests': tests_require},
    cmdclass={'test': PyTest},
    test_suite='tests',
    include_package_data=True,
    entry_points={
        'paste.filter_app_factory': [
            'opbeat = opbeat.contrib.paste:opbeat_filter_factory',
        ],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
)
