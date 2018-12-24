from elasticapm.instrumentation.packages.dbapi2 import Literal, extract_signature, scan, tokenize


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


def test_scan_double_quotes_at_end():
    sql = """Hello Peter Pan at Disney 'World'"""
    tokens = tokenize(sql)
    actual = [t[1] for t in scan(tokens)]
    expected = ["Hello", "Peter", "Pan", "at", "Disney", Literal("'", "World")]
    assert actual == expected


def test_extract_signature_string():
    sql = "Hello 'Peter Pan' at Disney World"
    actual = extract_signature(sql)
    expected = "HELLO"
    assert actual == expected


def test_extract_signature_bytes():
    sql = b"Hello 'Peter Pan' at Disney World"
    actual = extract_signature(sql)
    expected = "HELLO"
    assert actual == expected
