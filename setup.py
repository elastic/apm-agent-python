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

from setuptools import setup, find_packages, Extension
from opbeat.version import VERSION
from setuptools.command.test import test as TestCommand

from distutils.command.build_ext import build_ext
from distutils.errors import (CCompilerError, DistutilsExecError,
                              DistutilsPlatformError)

if sys.platform == 'win32':
    build_ext_errors = (CCompilerError, DistutilsExecError,
                        DistutilsPlatformError, IOError)
else:
    build_ext_errors = (CCompilerError, DistutilsExecError,
                        DistutilsPlatformError)


class BuildExtFailed(Exception):
    pass


class optional_build_ext(build_ext):
    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            raise BuildExtFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except build_ext_errors:
            raise BuildExtFailed()

tests_require = [
    'py>=1.4.26',
    'pytest>=2.6.4',
    'pytest-django==2.8.0',
    'pytest-capturelog>=0.7',
    'blinker>=1.1',
    'celery',
    'django-celery',
    'Flask>=0.8',
    'logbook',
    'mock',
    'pep8',
    'webob',
    'pytz',
    'redis',
    'urllib3',
    'jinja2',
    'pytest-benchmark',
]

if sys.version_info[0] == 2:
    tests_require += [
        'unittest2',
        'gevent',
        'zerorpc>=0.4.0,<0.5',
        'python-memcached'
    ]
else:
    tests_require += ['python3-memcached']


if sys.version_info[:2] == (2, 6):
    tests_require += ['Django>=1.2,<1.7']
else:
    tests_require += ['Django>=1.2']

try:
    import __pypy__
except ImportError:
    if sys.version_info[0] == 2:
        tests_require += ['zerorpc>=0.4.0,<0.5']
    tests_require += ['psycopg2']


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


setup_kwargs = dict(
    name='opbeat',
    version=VERSION,
    author='Opbeat, Inc',
    author_email='support@opbeat.com',
    url='https://github.com/opbeat/opbeat_python',
    description='The official Python module for Opbeat.com',
    long_description=open(os.path.join(os.path.dirname(__file__), 'README.rst')).read(),
    packages=find_packages(exclude=("tests",)),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'tests': tests_require, 'flask': ['blinker']},
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


def run_setup(with_extensions):
    setup_kwargs_tmp = dict(setup_kwargs)

    if with_extensions:
        setup_kwargs_tmp['ext_modules'] = [Extension(
            'opbeat.utils.wrapt._wrappers', ['opbeat/utils/wrapt/_wrappers.c']
        )]
        setup_kwargs_tmp['cmdclass']['build_ext'] = optional_build_ext

    setup(**setup_kwargs_tmp)

try:
    run_setup(with_extensions=True)

except BuildExtFailed:
    run_setup(with_extensions=False)
