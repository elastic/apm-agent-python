# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.db import models
from django import VERSION as DJANGO_VERSION


if DJANGO_VERSION >= (1, 5):
    from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

    class MyUser(AbstractBaseUser):
        USERNAME_FIELD = 'my_username'
        my_username = models.CharField(max_length=30)

        objects = BaseUserManager()

        class Meta:
            abstract = False
