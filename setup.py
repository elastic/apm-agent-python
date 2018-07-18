#!/usr/bin/env python
"""
elasticapm
======

elastic-apm is a Python client for `Elastic APM <https://elastic.co/apm>`_. It provides
full out-of-the-box support for many of the popular frameworks, including
`Django <djangoproject.com>`_, `Flask <http://flask.pocoo.org/>`_, and `Pylons
<http://www.pylonsproject.org/>`_. elastic-apm also includes drop-in support for any
`WSGI <http://wsgi.readthedocs.org/>`_-compatible web application.
"""

# Hack to prevent stupid "TypeError: 'NoneType' object is not callable" error
# in multiprocessing/util.py _exit_function when running `python
# setup.py test` (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
for m in ("multiprocessing", "billiard"):
    try:
        __import__(m)
    except ImportError:
        pass

import sys
import os
import ast
from codecs import open

from setuptools import setup, find_packages, Extension
from setuptools.command.test import test as TestCommand

from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError

if sys.platform == "win32":
    build_ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError)
else:
    build_ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)


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


def get_version():
    """
    Get version without importing from elasticapm. This avoids any side effects
    from importing while installing and/or building the module
    :return: a string, indicating the version
    """
    version_file = open(os.path.join("elasticapm", "version.py"), encoding="utf-8")
    for line in version_file:
        if line.startswith("__version__"):
            version_tuple = ast.literal_eval(line.split(" = ")[1])
            return ".".join(map(str, version_tuple))
    return "unknown"


tests_require = [
    "py>=1.4.26",
    "pytest>=2.6.4",
    "pytest-django==2.8.0",
    "pytest-capturelog>=0.7",
    "blinker>=1.1",
    "celery",
    "django-celery",
    "Flask>=0.8",
    "logbook",
    "mock",
    "pep8",
    "webob",
    "pytz",
    "redis",
    "requests",
    "jinja2",
    "pytest-benchmark",
    "urllib3-mock",
    "Twisted",
    # isort
    "apipkg",
    "execnet",
    "isort",
    "pytest-cache",
    "pytest-isort",
]

if sys.version_info[0] == 2:
    tests_require += ["unittest2", "gevent", "zerorpc>=0.4.0,<0.5", "python-memcached"]
else:
    tests_require += ["python3-memcached"]


try:
    import __pypy__
except ImportError:
    if sys.version_info[0] == 2 and "SKIP_ZERORPC" not in os.environ:
        tests_require += ["zerorpc>=0.4.0,<0.5"]
    tests_require += ["psycopg2"]

if sys.version_info >= (3, 5):
    tests_require += ["aiohttp", "pytest-asyncio", "pytest-mock"]

install_requires = ["urllib3", "certifi", "cachetools;python_version=='2.7'"]


class PyTest(TestCommand):
    user_options = [("pytest-args=", "a", "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest

        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


setup_kwargs = dict(
    name="elastic-apm",
    version=get_version(),
    author="Elastic, Inc",
    license="BSD",
    url="https://github.com/elastic/apm-agent-python",
    description="The official Python module for Elastic APM",
    long_description=open(os.path.join(os.path.dirname(__file__), "README.rst"), encoding="utf-8").read(),
    packages=find_packages(exclude=("tests",)),
    zip_safe=False,
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={"tests": tests_require, "flask": ["blinker"], "asyncio": ["aiohttp"]},
    cmdclass={"test": PyTest},
    test_suite="tests",
    include_package_data=True,
    entry_points={"paste.filter_app_factory": ["elasticapm = elasticapm.contrib.paste:filter_factory"]},
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Operating System :: OS Independent",
        "Topic :: Software Development",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)


def run_setup(with_extensions):
    setup_kwargs_tmp = dict(setup_kwargs)

    if with_extensions:
        setup_kwargs_tmp["ext_modules"] = [
            Extension("elasticapm.utils.wrapt._wrappers", ["elasticapm/utils/wrapt/_wrappers.c"])
        ]
        setup_kwargs_tmp["cmdclass"]["build_ext"] = optional_build_ext

    setup(**setup_kwargs_tmp)


# Figure out if we should build the wrapt C extensions

with_extensions = os.environ.get("ELASTIC_APM_WRAPT_EXTENSIONS", None)

if with_extensions:
    if with_extensions.lower() == "true":
        with_extensions = True
    elif with_extensions.lower() == "false":
        with_extensions = False
    else:
        with_extensions = None

if hasattr(sys, "pypy_version_info"):
    with_extensions = False

if with_extensions is None:
    with_extensions = True

try:
    run_setup(with_extensions=with_extensions)
except BuildExtFailed:
    run_setup(with_extensions=False)
