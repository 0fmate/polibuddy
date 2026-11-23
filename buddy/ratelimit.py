"""A small in-memory rate limiter per client IP, to protect the public demo's free API quota."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from . import config

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def allow(ip: str, limit: int | None = None, window: float = 60.0) -> bool:
    limit = config.RATE_LIMIT_PER_MINUTE if limit is None else limit
    if limit <= 0:
        return True
    now = time.monotonic()
    with _lock:
        q = _hits[ip]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(_hits) > 10000:  # drop idle clients
            for key in [k for k, v in _hits.items() if not v]:
                del _hits[key]
        return True
