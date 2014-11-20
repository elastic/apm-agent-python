from opbeat.contrib.async import AsyncClient
from opbeat.contrib.django import DjangoClient


class AsyncDjangoClient(AsyncClient, DjangoClient):
    pass
