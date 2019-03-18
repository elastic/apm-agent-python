def assert_any_record_contains(records, message):
    assert any(message in record.message for record in records)
