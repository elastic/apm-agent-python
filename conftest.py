#!/usr/bin/env python

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

import importlib
import os
import sys
from os.path import abspath, dirname

try:
    import eventlet

    eventlet.monkey_patch()
except ImportError:
    pass

try:
    from psycopg2cffi import compat

    compat.register()
except ImportError:
    pass

where_am_i = dirname(abspath(__file__))


sys.path.insert(0, where_am_i)

# don't run tests of dependencies that land in "build" and "src"
collect_ignore = ["build", "src"]

pytest_plugins = ["tests.fixtures"]

for module, fixtures in {
    "django": "tests.contrib.django.fixtures",
    "flask": "tests.contrib.flask.fixtures",
    "aiohttp": "aiohttp.pytest_plugin",
    "sanic": "tests.contrib.sanic.fixtures",
}.items():
    try:
        importlib.import_module(module)
        pytest_plugins.append(fixtures)
    except ImportError:
        pass


def pytest_report_header(config):
    if "PYTHON_VERSION" in os.environ:
        return "matrix: {}/{}".format(os.environ.get("PYTHON_VERSION"), os.environ.get("WEBFRAMEWORK"))
