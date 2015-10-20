from opbeat.instrumentation.packages.dbapi2 import Literal, scan, tokenize


def test_scan_simple():
    sql = "Hello 'Peter Pan' at Disney World"
    tokens = tokenize(sql)
    actual = [t[1] for t in scan(tokens)]
    expected = ["Hello", Literal("'", "Peter Pan"), "at", "Disney", "World"]
    assert actual == expected


def test_scan_with_escape_single_quote():
    sql = "Hello 'Peter\\' Pan' at Disney World"
    tokens = tokenize(sql)
    actual = [t[1] for t in scan(tokens)]
    expected = ["Hello", Literal("'", "Peter' Pan"), "at", "Disney", "World"]
    assert actual == expected


def test_scan_with_escape_slash():
    sql = "Hello 'Peter Pan\\\\' at Disney World"
    tokens = tokenize(sql)
    actual = [t[1] for t in scan(tokens)]
    expected = ["Hello", Literal("'", "Peter Pan\\"), "at", "Disney", "World"]
    assert actual == expected


def test_scan_double_quotes():
    sql = """Hello 'Peter'' Pan''' at Disney World"""
    tokens = tokenize(sql)
    actual = [t[1] for t in scan(tokens)]
    expected = ["Hello", Literal("'", "Peter' Pan'"), "at", "Disney", "World"]
    assert actual == expected
