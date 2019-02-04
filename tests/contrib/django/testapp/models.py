# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class MyUser(AbstractBaseUser):
    USERNAME_FIELD = "my_username"
    my_username = models.CharField(max_length=30)

    objects = BaseUserManager()

    class Meta:
        abstract = False


class MyIntUser(AbstractBaseUser):
    USERNAME_FIELD = "my_username"

    my_username = models.IntegerField()

    objects = BaseUserManager()

    class Meta:
        abstract = False
