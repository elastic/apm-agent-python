# -*- coding: utf-8 -*-

from __future__ import absolute_import

try:
    from .celery import app as celery_app
except ImportError:
    # celery not installed
    pass
