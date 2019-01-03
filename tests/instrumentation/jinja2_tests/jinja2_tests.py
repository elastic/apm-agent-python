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
