import os

import mock
import pytest
from jinja2 import Environment, FileSystemLoader
from jinja2.environment import Template


@pytest.fixture()
def jinja_env():
    filedir = os.path.dirname(__file__)
    loader = FileSystemLoader(filedir)
    return Environment(loader=loader)


@mock.patch("elasticapm.traces.TransactionsStore.should_collect")
def test_from_file(should_collect, jinja_env, elasticapm_client):
    should_collect.return_value = False
    elasticapm_client.begin_transaction("transaction.test")
    template = jinja_env.get_template('mytemplate.html')
    template.render()
    elasticapm_client.end_transaction("MyView")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'mytemplate.html'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == 'mytemplate.html'
    assert traces[0]['type'] == 'template.jinja2'


def test_from_string(elasticapm_client):
    elasticapm_client.begin_transaction("transaction.test")
    template = Template("<html></html")
    template.render()
    elasticapm_client.end_transaction("test")

    transactions = elasticapm_client.instrumentation_store.get_all()
    traces = transactions[0]['traces']

    expected_signatures = {'<template>'}

    assert {t['name'] for t in traces} == expected_signatures

    assert traces[0]['name'] == '<template>'
    assert traces[0]['type'] == 'template.jinja2'
