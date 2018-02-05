import mock
import pytest

from elasticapm.utils import compat

try:
    from werkzeug.datastructures import MultiDict
    has_multidict = True
except ImportError:
    has_multidict = False

try:
    from django.utils.datastructures import MultiValueDict
    has_multivaluedict = True
except ImportError:
    has_multivaluedict = False




@mock.patch('platform.system')
@mock.patch('platform.python_implementation')
@mock.patch('platform.python_version_tuple')
def test_default_library_paths(version_tuple, python_implementation, system):
    cases = (
        ('Linux', ('3', '5', '1'), 'CPython', ['*/lib/python3.5/*', '*/lib64/python3.5/*']),
        ('Linux', ('2', '7', '9'), 'CPython', ['*/lib/python2.7/*', '*/lib64/python2.7/*']),
        ('Windows', ('3', '5', '1'), 'CPython', ['*\\lib\\*']),
        ('Windows', ('2', '7', '9'), 'CPython', ['*\\lib\\*']),
        ('Linux', ('3', '6', '3'), 'PyPy', ['*/lib-python/3/*', '*/site-packages/*']),
        ('Linux', ('2', '7', '9'), 'PyPy', ['*/lib-python/2.7/*', '*/site-packages/*']),
    )
    for system_name, version, implementation, expected in cases:
        system.return_value = system_name
        version_tuple.return_value = version
        python_implementation.return_value = implementation

        assert compat.get_default_library_patters() == expected


@pytest.mark.skipif(not has_multivaluedict, reason='Django not installed')
def test_multivalue_dict():
    d = MultiValueDict()
    d.update({'a': 'b', 'b': 'd'})
    d.update({'a': 'c', 'e': 'f'})
    d = compat.multidict_to_dict(d)
    assert d == {'a': ['b', 'c'], 'b': 'd', 'e': 'f'}


@pytest.mark.skipif(not has_multidict, reason='Werkzeug not installed')
def test_multi_dict():
    d = MultiDict()
    d.update({'a': 'b', 'b': 'd'})
    d.update({'a': 'c', 'e': 'f'})
    d = compat.multidict_to_dict(d)
    assert d == {'a': ['b', 'c'], 'b': 'd', 'e': 'f'}
