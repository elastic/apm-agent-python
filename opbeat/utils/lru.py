"""
Backported LRU cache from Python 3.3
http://code.activestate.com/recipes/578078-py26-and-py30-backport-of-python-33s-lru-cache/

"""
from collections import namedtuple
from threading import RLock

_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])


class LRUCache(object):
    def __init__(self, maxsize=100):
        self.cache = dict()
        self.cache_get = self.cache.get           # bound method to lookup key or return None
        self._len = len                      # localize the global len() function
        self.lock = RLock()                  # because linkedlist updates aren't threadsafe
        self.root = []                       # root of the circular doubly linked list
        self.root[:] = [self.root, self.root, None]      # initialize by pointing to self
        self.nonlocal_root = [self.root]                  # make updateable non-locally
        self.PREV, self.NEXT, self.KEY = 0, 1, 2    # names for the link fields
        self.maxsize = maxsize

    def __contains__(self, key):
        with self.lock:
            link = self.cache_get(key)
            if link is not None:
                # record recent use of the key by moving it to the front of the list
                root, = self.nonlocal_root
                link_prev, link_next, key = link
                link_prev[self.NEXT] = link_next
                link_next[self.PREV] = link_prev
                last = root[self.PREV]
                last[self.NEXT] = root[self.PREV] = link
                link[self.PREV] = last
                link[self.NEXT] = root

                return True
        return False

    def set(self, key):
        with self.lock:
            root, = self.nonlocal_root
            if key in self.cache:
                # getting here means that this same key was added to the
                # cache while the lock was released.  since the link
                # update is already done, we need only return the
                # computed result and update the count of misses.
                pass
            elif self._len(self.cache) >= self.maxsize:
                # use the old root to store the new key and result
                oldroot = root
                oldroot[self.KEY] = key
                # empty the oldest link and make it the new root
                root = self.nonlocal_root[0] = oldroot[self.NEXT]
                oldkey = root[self.KEY]
                root[self.KEY] = None
                # now update the cache dictionary for the new links
                del self.cache[oldkey]
                self.cache[key] = oldroot
            else:
                # put result in a new link at the front of the list
                last = root[self.PREV]
                link = [last, root, key]
                last[self.NEXT] = root[self.PREV] = self.cache[key] = link
