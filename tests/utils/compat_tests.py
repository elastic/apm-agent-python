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

import mock
import pytest

from elasticapm.utils import compat

try:
    from werkzeug.datastructures import MultiDict

    has_multidict = True
except ImportError:
    has_multidict = False

try:
    from django.utils.datastructures import MultiValueDict

    has_multivaluedict = True
except ImportError:
    has_multivaluedict = False


@mock.patch("platform.system")
@mock.patch("platform.python_implementation")
@mock.patch("platform.python_version_tuple")
def test_default_library_paths(version_tuple, python_implementation, system):
    cases = (
        ("Linux", ("3", "5", "1"), "CPython", ["*/lib/python3.5/*", "*/lib64/python3.5/*"]),
        ("Linux", ("2", "7", "9"), "CPython", ["*/lib/python2.7/*", "*/lib64/python2.7/*"]),
        ("Windows", ("3", "5", "1"), "CPython", ["*\\lib\\*"]),
        ("Windows", ("2", "7", "9"), "CPython", ["*\\lib\\*"]),
        ("Linux", ("3", "6", "3"), "PyPy", ["*/lib-python/3/*", "*/site-packages/*"]),
        ("Linux", ("2", "7", "9"), "PyPy", ["*/lib-python/2.7/*", "*/site-packages/*"]),
    )
    for system_name, version, implementation, expected in cases:
        system.return_value = system_name
        version_tuple.return_value = version
        python_implementation.return_value = implementation

        assert compat.get_default_library_patters() == expected


@pytest.mark.django
@pytest.mark.skipif(not has_multivaluedict, reason="Django not installed")
def test_multivalue_dict():
    d = MultiValueDict()
    d.update({"a": "b", "b": "d"})
    d.update({"a": "c", "e": "f"})
    d = compat.multidict_to_dict(d)
    assert d == {"a": ["b", "c"], "b": "d", "e": "f"}


@pytest.mark.flask
@pytest.mark.skipif(not has_multidict, reason="Werkzeug not installed")
def test_multi_dict():
    d = MultiDict()
    d.update({"a": "b", "b": "d"})
    d.update({"a": "c", "e": "f"})
    d = compat.multidict_to_dict(d)
    assert d == {"a": ["b", "c"], "b": "d", "e": "f"}
