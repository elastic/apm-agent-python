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

import ast
import codecs
import os

from setuptools import setup


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
            version_str = ".".join(map(str, version_tuple))
            post_version = os.getenv("ELASTIC_CI_POST_VERSION")
            if post_version:
                return f"{version_str}.post{post_version}"
            return version_str
    return "unknown"


setup(version=get_version())
