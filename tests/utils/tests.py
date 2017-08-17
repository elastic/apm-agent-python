from elasticapm.utils.deprecation import deprecated


@deprecated("alternative")
def deprecated_function():
    pass


def test_deprecation():
    deprecated_function()
