# -*- coding: utf-8 -*-

from elasticapm.transport.http import AsyncHTTPTransport, HTTPTransport


default = [HTTPTransport, AsyncHTTPTransport]
