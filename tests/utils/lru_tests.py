from __future__ import absolute_import

from elasticapm.utils.lru import LRUCache
from tests.utils.compat import TestCase


class LRUTest(TestCase):
    def test_insert_overflow(self):

        lru = LRUCache(4)

        for x in range(6):
            lru.set(x)

        self.assertNotIn(1, lru)
        for x in range(2, 6):
            self.assertIn(x, lru)
