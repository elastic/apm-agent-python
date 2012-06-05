# -*- coding: utf-8 -*-

from unittest2 import TestCase

import opbeat_python
from opbeat_python.utils import get_versions


class GetVersionsTest(TestCase):
    def test_exact_match(self):
        versions = get_versions(['opbeat_python'])
        self.assertEquals(versions.get('opbeat_python'), opbeat_python.VERSION)

    def test_parent_match(self):
        versions = get_versions(['opbeat_python.contrib.django'])
        self.assertEquals(versions.get('opbeat_python'), opbeat_python.VERSION)
