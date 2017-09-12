# -*- coding: utf-8 -*-

from elasticapm.transport.http_urllib3 import AsyncUrllib3Transport, Urllib3Transport


default = [Urllib3Transport, AsyncUrllib3Transport]
