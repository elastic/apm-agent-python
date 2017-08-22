import pytest

from tests.helpers import get_tempstoreclient


@pytest.fixture()
def test_client():
    return get_tempstoreclient()
