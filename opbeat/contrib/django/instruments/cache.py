from django.core import cache
from django.core.cache import cache as original_cache, get_cache as original_get_cache
from django.core.cache.backends.base import BaseCache
import time
from opbeat.contrib.django.instruments.aggr import instrumentation, TimedCall
from opbeat.utils.stacks import get_stack_info
from opbeat.utils.stacks import iter_stack_frames


def send_signal(method):
    def wrapped(self, *args, **kwargs):
        with instrumentation.time(method.__name__, "cache", None,
                                  {"args": args,
                                   "kwargs": kwargs}):
            return method(self, *args, **kwargs)

    return wrapped


class CacheStatTracker(BaseCache):
    """A small class used to track cache calls."""
    def __init__(self, cache):
        self.cache = cache

    def __repr__(self):
        return str("<CacheStatTracker for %s>") % repr(self.cache)

    def __contains__(self, key):
        return self.cache.__contains__(key)

    def __getattr__(self, name):
        return getattr(self.cache, name)

    @send_signal
    def add(self, *args, **kwargs):
        return self.cache.add(*args, **kwargs)

    @send_signal
    def get(self, *args, **kwargs):
        return self.cache.get(*args, **kwargs)

    @send_signal
    def set(self, *args, **kwargs):
        return self.cache.set(*args, **kwargs)

    @send_signal
    def delete(self, *args, **kwargs):
        return self.cache.delete(*args, **kwargs)

    @send_signal
    def has_key(self, *args, **kwargs):
        # Ignore flake8 rules for has_key since we need to support caches
        # that may be using has_key.
        return self.cache.has_key(*args, **kwargs)  # noqa

    @send_signal
    def incr(self, *args, **kwargs):
        return self.cache.incr(*args, **kwargs)

    @send_signal
    def decr(self, *args, **kwargs):
        return self.cache.decr(*args, **kwargs)

    @send_signal
    def get_many(self, *args, **kwargs):
        return self.cache.get_many(*args, **kwargs)

    @send_signal
    def set_many(self, *args, **kwargs):
        self.cache.set_many(*args, **kwargs)

    @send_signal
    def delete_many(self, *args, **kwargs):
        self.cache.delete_many(*args, **kwargs)

    @send_signal
    def incr_version(self, *args, **kwargs):
        return self.cache.incr_version(*args, **kwargs)

    @send_signal
    def decr_version(self, *args, **kwargs):
        return self.cache.decr_version(*args, **kwargs)


def get_cache(*args, **kwargs):
    return CacheStatTracker(original_get_cache(*args, **kwargs))


def enable_instrumentation():
    # This isn't thread-safe because cache connections aren't thread-local
    # in Django, unlike database connections.
    cache.cache = CacheStatTracker(original_cache)
    cache.get_cache = get_cache
