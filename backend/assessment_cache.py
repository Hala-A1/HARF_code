"""Bounded private process caches; keys are digests, never raw source text."""
from collections import OrderedDict
from copy import deepcopy
from threading import Event, RLock
import hashlib
import json
import time


def fingerprint(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


class AssessmentCache:
    def __init__(self, maximum=128, ttl=1800, byte_limit=8 * 1024 * 1024):
        self.maximum, self.ttl, self.byte_limit = maximum, ttl, byte_limit
        self.lock = RLock()
        self.entries, self.pending = OrderedDict(), {}
        self.size = 0

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.size = 0

    def get_or_compute(self, key, compute, cacheable=lambda value: True):
        with self.lock:
            found = self.entries.get(key)
            if found and found[0] > time.monotonic():
                self.entries.move_to_end(key)
                return deepcopy(found[1]), True
            if found:
                self.size -= self.entries.pop(key)[2]
            owner = key not in self.pending
            if owner:
                self.pending[key] = {'event': Event()}
            flight = self.pending[key]
        if not owner:
            if not flight['event'].wait(150):
                raise TimeoutError('The shared assessment took too long. Please retry.')
            if 'error' in flight:
                raise flight['error']
            return deepcopy(flight['value']), True
        try:
            value = compute()
            size = len(json.dumps(value, ensure_ascii=False).encode('utf-8'))
            with self.lock:
                if size <= self.byte_limit and cacheable(value):
                    self.entries[key] = (time.monotonic() + self.ttl, value, size)
                    self.size += size
                    while len(self.entries) > self.maximum or self.size > self.byte_limit:
                        self.size -= self.entries.popitem(last=False)[1][2]
                flight['value'] = value
            return deepcopy(value), False
        except BaseException as error:
            flight['error'] = error
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)
                flight['event'].set()


SOURCE_FACTS = AssessmentCache()
OUTPUT_REVIEWS = AssessmentCache()
