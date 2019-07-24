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

import os

import pytest
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template

from elasticapm.conf.constants import TRANSACTION


@pytest.fixture()
def jinja_env():
    filedir = os.path.dirname(__file__)
    loader = FileSystemLoader(filedir)
    return Environment(loader=loader)


def test_from_file(instrument, jinja_env, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    template = jinja_env.get_template("mytemplate.html")
    template.render()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"mytemplate.html"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "mytemplate.html"
    assert spans[0]["type"] == "template"
    assert spans[0]["subtype"] == "jinja2"
    assert spans[0]["action"] == "render"


def test_from_string(instrument, elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    template = Template("<html></html")
    template.render()
    elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.events[TRANSACTION]
    spans = elasticapm_client.spans_for_transaction(transactions[0])

    expected_signatures = {"<template>"}

    assert {t["name"] for t in spans} == expected_signatures

    assert spans[0]["name"] == "<template>"
    assert spans[0]["type"] == "template"
    assert spans[0]["subtype"] == "jinja2"
    assert spans[0]["action"] == "render"
