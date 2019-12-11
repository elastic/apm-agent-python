#  BSD 3-Clause License
#
#  Copyright (c) 2019, Elasticsearch BV
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  * Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#  DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#  FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#  DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#  OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import pytest  # isort:skip

pytest.importorskip("django")  # isort:skip

from os.path import join

import django
from django.test.utils import override_settings

import pytest

from elasticapm.conf.constants import TRANSACTION
from tests.contrib.django.conftest import BASE_TEMPLATE_DIR
from tests.utils.compat import middleware_setting

try:
    # Django 1.10+
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse

pytestmark = pytest.mark.django

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

    kinds = ["code", "template"]
    assert set([t["type"] for t in spans]) == set(kinds)

    assert spans[0]["type"] == "code"
    assert spans[0]["name"] == "something_expensive"
    assert spans[0]["parent_id"] == spans[1]["id"]

    assert spans[1]["type"] == "template"
    assert spans[1]["subtype"] == "django"
    assert spans[1]["action"] == "render"
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

    kinds = ["template"]
    assert set([t["type"] for t in spans]) == set(kinds)

    assert spans[0]["type"] == "template"
    assert spans[0]["subtype"] == "jinja2"
    assert spans[0]["action"] == "render"
    assert spans[0]["name"] == "jinja2_template.html"
    assert spans[0]["parent_id"] == transactions[0]["id"]
