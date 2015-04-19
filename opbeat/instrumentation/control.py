from opbeat.instrumentation.packages.requests import RequestsInstrumentation
from opbeat.instrumentation.packages.pylibmc import PyLibMcInstrumentation
from opbeat.instrumentation.packages.django.template import DjangoTemplateInstrumentation
from opbeat.instrumentation.packages.psycopg2 import Psycopg2Instrumentation

def instrument(client):
    for cls in [RequestsInstrumentation, PyLibMcInstrumentation,
                DjangoTemplateInstrumentation, Psycopg2Instrumentation]:

        cls(client).instrument()