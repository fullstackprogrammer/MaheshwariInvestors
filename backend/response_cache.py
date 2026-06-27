"""
In-memory TTL cache for precomputed API responses (rankings, stocks, metrics).
Invalidated when the stock data cache refreshes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)

_lock = threading.Lock()
_store: Dict[str, Tuple[float, Any]] = {}


def get(key: str, ttl_sec: float) -> Optional[Any]:
    with _lock:
        entry = _store.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            _store.pop(key, None)
            return None
        return value


def set(key: str, value: Any, ttl_sec: float) -> None:
    with _lock:
        _store[key] = (time.time() + ttl_sec, value)


def invalidate_all() -> None:
    with _lock:
        count = len(_store)
        _store.clear()
    if count:
        log.info("[Response cache] Cleared %s entries", count)


def stats() -> Dict[str, int]:
    with _lock:
        return {"entries": len(_store)}
