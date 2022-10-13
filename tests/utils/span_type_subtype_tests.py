#  BSD 3-Clause License
#
#  Copyright (c) 2022, Elasticsearch BV
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

import pytest

import elasticapm


def test_span_type_not_found(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(UserWarning, match='Span type "bar" not found in JSON spec'):
        with elasticapm.capture_span("foo", span_type="bar"):
            pass
    elasticapm_client.end_transaction("test")


def test_span_type_no_subtypes(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(UserWarning, match='Span type "process" has no subtypes, but subtype "foo" is set'):
        with elasticapm.capture_span("foo", span_type="process", span_subtype="foo"):
            pass
    elasticapm_client.end_transaction("test")


def test_span_type_subtype_not_allowed(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(UserWarning, match='Subtype "anonexistingdb" not allowed for span type "db"'):
        with elasticapm.capture_span("foo", span_type="db", span_subtype="anonexistingdb"):
            pass
    elasticapm_client.end_transaction("test")


def test_span_type_not_used_by_python(elasticapm_client):
    elasticapm_client.begin_transaction("test")
    with pytest.warns(UserWarning, match='"json.parse" not marked as used by Python'):
        with elasticapm.capture_span("foo", span_type="json", span_subtype="parse"):
            pass
    elasticapm_client.end_transaction("test")
