#  BSD 3-Clause License
#
#  Copyright (c) 2023, Elasticsearch BV
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

# Unfortunately, we can't really do a full end-to-end test for auto-instrumenting Django.
# Installing an app is not reversible, so using this instrumentation "for real" would
# pollute the Django instance used by pytest.

import mock

from elasticapm.instrumentation.packages.django import DjangoAutoInstrumentation


def test_populate_wrapper_args():
    populate_wrapper = DjangoAutoInstrumentation()
    wrapped = mock.Mock()
    populate_wrapper.call(None, None, wrapped, None, [["django.contrib.admin", "django.contrib.auth"]], {})
    assert wrapped.call_count == 1
    args = wrapped.call_args.args
    assert len(args[0]) == 3
    assert args[0][0] == "elasticapm.contrib.django"


def test_populate_wrapper_args_already_set():
    populate_wrapper = DjangoAutoInstrumentation()
    wrapped = mock.Mock()
    populate_wrapper.call(
        None, None, wrapped, None, [["django.contrib.admin", "django.contrib.auth", "elasticapm.contrib.django"]], {}
    )
    assert wrapped.call_count == 1
    args = wrapped.call_args.args
    assert len(args[0]) == 3
    assert args[0][2] == "elasticapm.contrib.django"


def test_populate_wrapper_kwargs():
    populate_wrapper = DjangoAutoInstrumentation()
    wrapped = mock.Mock()
    populate_wrapper.call(
        None, None, wrapped, None, [], {"installed_apps": ["django.contrib.admin", "django.contrib.auth"]}
    )
    assert wrapped.call_count == 1
    kwargs = wrapped.call_args.kwargs
    assert len(kwargs["installed_apps"]) == 3
    assert kwargs["installed_apps"][0] == "elasticapm.contrib.django"


def test_populate_wrapper_kwargs_already_set():
    populate_wrapper = DjangoAutoInstrumentation()
    wrapped = mock.Mock()
    populate_wrapper.call(
        None,
        None,
        wrapped,
        None,
        [],
        {"installed_apps": ["django.contrib.admin", "django.contrib.auth", "elasticapm.contrib.django"]},
    )
    assert wrapped.call_count == 1
    kwargs = wrapped.call_args.kwargs
    assert len(kwargs["installed_apps"]) == 3
    assert kwargs["installed_apps"][2] == "elasticapm.contrib.django"
