from __future__ import absolute_import

from opbeat.utils.lru import LRUCache
from tests.utils.compat import TestCase


class LRUTest(TestCase):
    def test_insert_overflow(self):

        lru = LRUCache(4)

        for x in range(6):
            lru.set(x)

        self.assertFalse(lru.has_key(1))
        for x in range(2, 6):
            self.assertTrue(lru.has_key(x))
