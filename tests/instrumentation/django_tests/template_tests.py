import pytest  # isort:skip

pytest.importorskip("django")  # isort:skip

from os.path import join

import django
from django.test.utils import override_settings

import mock
import pytest

from conftest import BASE_TEMPLATE_DIR
from elasticapm.conf.constants import TRANSACTION
from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse


# Testing Django 1.8+ backends
TEMPLATES = (
    {"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_TEMPLATE_DIR]},
    {"BACKEND": "django.template.backends.jinja2.Jinja2", "DIRS": [join(BASE_TEMPLATE_DIR, "jinja2")]},
)


def test_template_rendering(instrument, django_elasticapm_client, client):
    with override_settings(
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get(reverse("render-heavy-template"))
        client.get(reverse("render-heavy-template"))
        client.get(reverse("render-heavy-template"))

    transactions = django_elasticapm_client.events[TRANSACTION]

    assert len(transactions) == 3
    spans = django_elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 2, [t["name"] for t in spans]

    kinds = ["code", "template.django"]
    assert set([t["type"] for t in spans]) == set(kinds)

    assert spans[0]["type"] == "code"
    assert spans[0]["name"] == "something_expensive"
    assert spans[0]["parent_id"] == spans[1]["id"]

    assert spans[1]["type"] == "template.django"
    assert spans[1]["name"] == "list_users.html"
    assert spans[1]["parent_id"] == transactions[0]["id"]


@pytest.mark.skipif(django.VERSION < (1, 8), reason="Jinja2 support introduced with Django 1.8")
def test_template_rendering_django18_jinja2(instrument, django_elasticapm_client, client):
    with override_settings(
        TEMPLATES=TEMPLATES,
        **middleware_setting(django.VERSION, ["elasticapm.contrib.django.middleware.TracingMiddleware"])
    ):
        client.get(reverse("render-jinja2-template"))
        client.get(reverse("render-jinja2-template"))
        client.get(reverse("render-jinja2-template"))

    transactions = django_elasticapm_client.events[TRANSACTION]

    assert len(transactions) == 3
    spans = django_elasticapm_client.spans_for_transaction(transactions[0])
    assert len(spans) == 1, [t["name"] for t in spans]

    kinds = ["template.jinja2"]
    assert set([t["type"] for t in spans]) == set(kinds)

    assert spans[0]["type"] == "template.jinja2"
    assert spans[0]["name"] == "jinja2_template.html"
    assert spans[0]["parent_id"] == transactions[0]["id"]
