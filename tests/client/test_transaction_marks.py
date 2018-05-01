import time

import pytest

import elasticapm


def test_basic_mark(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    elasticapm.mark('test_group', 'test')
    elasticapm_client.end_transaction('test')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    assert transaction['marks']['test_group']['test'] > 0


def test_basic_multiple_mark_with_override(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    elasticapm.mark('test_group', 'test')
    time.sleep(0.1)
    elasticapm.mark('test_group', 'test')
    elasticapm_client.end_transaction('test')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    assert transaction['marks']['test_group']['test'] > 0.1
    assert len(transaction['marks']['test_group']) == 1


def test_basic_multiple_mark_without_override(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    for i in range(5):
        elasticapm.mark('test_group', 'test', override=False)
    elasticapm_client.end_transaction('test')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    assert transaction['marks']['test_group']['test'] > 0
    for i in range(1, 5):
        assert transaction['marks']['test_group']['test-%d' % i] > 0


def test_mark_while_no_transaction(elasticapm_client, caplog):
    elasticapm.mark('test_group', 'test')
    assert len(caplog.records) == 1
    assert "No transaction currently active" in caplog.records[0].message


@pytest.mark.parametrize('elasticapm_client', [
    {'transaction_mark_errors': 'all'},
    {'transaction_mark_errors': 'handled'},
    {'transaction_mark_errors': 'unhandled'},
    {'transaction_mark_errors': 'off'},
], indirect=True)
def test_mark_errors(elasticapm_client):
    elasticapm_client.begin_transaction('test')
    error_id_handled = elasticapm_client.capture_message('bla', handled=True)
    error_id_unhandled = elasticapm_client.capture_message('bla', handled=False)
    elasticapm_client.end_transaction('test')
    transaction = elasticapm_client.instrumentation_store.get_all()[0]
    if elasticapm_client.config.transaction_mark_errors == 'all':
        assert transaction['marks']['errors'][error_id_handled] > 0
        assert transaction['marks']['errors'][error_id_unhandled] > 0
    if elasticapm_client.config.transaction_mark_errors == 'handled':
        assert transaction['marks']['errors'][error_id_handled] > 0
        assert error_id_unhandled not in transaction['marks']['errors']
        assert len(transaction['marks']['errors']) == 1
    if elasticapm_client.config.transaction_mark_errors == 'unhandled':
        assert transaction['marks']['errors'][error_id_unhandled] > 0
        assert error_id_handled not in transaction['marks']['errors']
        assert len(transaction['marks']['errors']) == 1
    if elasticapm_client.config.transaction_mark_errors == 'off':
        # other marks could happen during this time, e.g. gc events, so we
        # need to check both possibilities
        assert not 'marks' in transaction or 'errors' not in transaction['marks']
