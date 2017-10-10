import pytest

from tests.helpers import get_tempstoreclient


@pytest.fixture()
def elasticapm_client():
    return get_tempstoreclient()
