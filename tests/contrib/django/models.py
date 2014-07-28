from __future__ import absolute_import
from opbeat.utils import six
from django.db import models


class DuplicateKeyModel(models.Model):
    foo = models.IntegerField(unique=True, default=1)

    def __unicode__(self):
        return six.text_type(self.foo)
