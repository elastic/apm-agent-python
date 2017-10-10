from __future__ import absolute_import

from elasticapm.utils.lru import LRUCache


def test_insert_overflow():

    lru = LRUCache(4)

    for x in range(6):
        lru.set(x)

    assert 1 not in lru
    for x in range(2, 6):
        assert x in lru
