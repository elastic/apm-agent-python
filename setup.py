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

#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Hack to prevent stupid "TypeError: 'NoneType' object is not callable" error
# in multiprocessing/util.py _exit_function when running `python
# setup.py test` (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
for m in ("multiprocessing", "billiard"):
    try:
        __import__(m)
    except ImportError:
        pass

import ast
import codecs
import os
import sys
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError

import pkg_resources
from setuptools import Extension, setup
from setuptools.command.test import test as TestCommand

pkg_resources.require("setuptools>=39.2")

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


def get_version():
    """
    Get version without importing from elasticapm. This avoids any side effects
    from importing while installing and/or building the module

    Once Python 3.8 is the lowest supported version, we could consider hardcoding
    the version in setup.cfg instead. 3.8 comes with importlib.metadata, which makes
    it trivial to find the version of a package, making it unnecessary to
    have the version available in code.

    :return: a string, indicating the version
    """
    version_file = codecs.open(os.path.join("elasticapm", "version.py"), encoding="utf-8")
    for line in version_file:
        if line.startswith("__version__"):
            version_tuple = ast.literal_eval(line.split(" = ")[1])
            return ".".join(map(str, version_tuple))
    return "unknown"


setup_kwargs = dict(cmdclass={"test": PyTest}, version=get_version())


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
