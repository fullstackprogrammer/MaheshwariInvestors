"""
File + in-memory cache for CSP screener data from yfinance.

TTLs reflect how fast each data type changes during the trading day.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / ".csp_cache"

# Slow-changing / structural
RAW_EXPIRATIONS_TTL_SEC = 86_400   # 24h — listed expiry dates
EARNINGS_TTL_SEC = 86_400          # 24h — next earnings date
INFO_TTL_SEC = 3_600               # 1h — sector, market cap, targets (refresh less often)

# Price-sensitive (TTLs apply only while the US market is OPEN)
FUNDAMENTALS_TTL_SEC = 900         # 15m — current price snapshot
OPTION_CHAIN_TTL_SEC = 900         # 15m — bid/ask/OI
SCREENER_RESULT_TTL_SEC = 600      # 10m — full screener output

# When the market is CLOSED, price-sensitive data is static, so cache it for
# much longer. The "mkt" flag stored on each entry forces a refresh when the
# market session flips (closed -> open), so we never serve stale closed data
# during live trading.
MARKET_CLOSED_TTL_SEC = 21_600     # 6h — static while market closed


def market_aware_ttl(open_ttl_sec: int, market_open: bool) -> int:
    """Short TTL while trading; long TTL when the market is closed (static data)."""
    return open_ttl_sec if market_open else MARKET_CLOSED_TTL_SEC

# Historical (intraday moves slowly)
HISTORY_1Y_TTL_SEC = 3_600         # 1h — shared for MA200 + IV rank
IV_RANK_TTL_SEC = 3_600            # 1h — derived from history
MA200_TTL_SEC = 3_600              # 1h — derived from history

_lock = threading.Lock()
_mem: Dict[str, tuple] = {}  # key -> (expires_at, data)


def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{digest}.json"


def get_cached(key: str, ttl_sec: int, market_open: Optional[bool] = None) -> Optional[Any]:
    now = time.time()
    with _lock:
        mem = _mem.get(key)
        if mem and mem[0] > now:
            return mem[1]
        if mem:
            _mem.pop(key, None)

    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        # Prefer the lifetime chosen at write time (e.g. long while market closed).
        eff_ttl = payload.get("ttl", ttl_sec)
        if now - payload.get("ts", 0) > eff_ttl:
            return None
        # Invalidate when the market session flips since the entry was written.
        if market_open is not None and "mkt" in payload and bool(payload["mkt"]) != bool(market_open):
            return None
        data = payload.get("data")
        with _lock:
            _mem[key] = (now + min(eff_ttl, 300), data)  # hot in-memory up to 5 min
        return data
    except Exception as e:
        log.debug("[CSP cache] read failed %s: %s", key, e)
        return None


def set_cached(key: str, data: Any, ttl_sec: int = 900, market_open: Optional[bool] = None) -> None:
    now = time.time()
    with _lock:
        _mem[key] = (now + min(ttl_sec, 300), data)
    path = _cache_path(key)
    payload = {"ts": now, "ttl": ttl_sec, "data": data}
    if market_open is not None:
        payload["mkt"] = bool(market_open)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as e:
        log.debug("[CSP cache] write failed %s: %s", key, e)


def clear_memory() -> None:
    with _lock:
        _mem.clear()


def stats() -> Dict[str, int]:
    with _lock:
        mem_entries = len(_mem)
    disk_entries = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0
    return {"memory_entries": mem_entries, "disk_entries": disk_entries}


# --- Ticker info (yfinance .info) ---

def get_ticker_info_cached(symbol: str) -> Optional[dict]:
    return get_cached(f"info:{symbol}", INFO_TTL_SEC)


def set_ticker_info_cached(symbol: str, info: dict) -> None:
    set_cached(f"info:{symbol}", info, INFO_TTL_SEC)


# --- Parsed fundamentals snapshot ---

def get_fundamentals_cached(symbol: str, market_open: Optional[bool] = None) -> Optional[dict]:
    return get_cached(f"fund:{symbol}", FUNDAMENTALS_TTL_SEC, market_open)


def set_fundamentals_cached(symbol: str, data: dict, market_open: Optional[bool] = None) -> None:
    ttl = market_aware_ttl(FUNDAMENTALS_TTL_SEC, market_open) if market_open is not None else FUNDAMENTALS_TTL_SEC
    set_cached(f"fund:{symbol}", data, ttl, market_open)


# --- 1y price history (slim: dates + close) ---

def get_history_1y_cached(symbol: str) -> Optional[dict]:
    return get_cached(f"hist1y:{symbol}", HISTORY_1Y_TTL_SEC)


def set_history_1y_cached(symbol: str, data: dict) -> None:
    set_cached(f"hist1y:{symbol}", data, HISTORY_1Y_TTL_SEC)


# --- Derived indicators ---

def get_ma200_cached(symbol: str) -> Optional[float]:
    data = get_cached(f"ma200:{symbol}", MA200_TTL_SEC)
    if data is None:
        return None
    return data.get("ma200")


def set_ma200_cached(symbol: str, ma200: Optional[float]) -> None:
    set_cached(f"ma200:{symbol}", {"ma200": ma200}, MA200_TTL_SEC)


def get_iv_rank_cached(symbol: str) -> Optional[float]:
    data = get_cached(f"ivrank:{symbol}", IV_RANK_TTL_SEC)
    if data is None:
        return None
    return data.get("iv_rank")


def set_iv_rank_cached(symbol: str, iv_rank: Optional[float]) -> None:
    set_cached(f"ivrank:{symbol}", {"iv_rank": iv_rank}, IV_RANK_TTL_SEC)


# --- Earnings ---

def get_earnings_cached(symbol: str) -> Optional[str]:
    data = get_cached(f"earnings:{symbol}", EARNINGS_TTL_SEC)
    if data is None:
        return None
    return data.get("earnings_date")


def set_earnings_cached(symbol: str, earnings_iso: Optional[str]) -> None:
    set_cached(f"earnings:{symbol}", {"earnings_date": earnings_iso}, EARNINGS_TTL_SEC)


# --- Options: raw expiration list + chains ---

def get_raw_expirations_cached(symbol: str) -> Optional[list]:
    return get_cached(f"expiries_raw:{symbol}", RAW_EXPIRATIONS_TTL_SEC)


def set_raw_expirations_cached(symbol: str, expirations: list) -> None:
    set_cached(f"expiries_raw:{symbol}", expirations, RAW_EXPIRATIONS_TTL_SEC)


def get_option_chain_cached(symbol: str, expiration: str, market_open: Optional[bool] = None) -> Optional[list]:
    return get_cached(f"chain:{symbol}:{expiration}", OPTION_CHAIN_TTL_SEC, market_open)


def set_option_chain_cached(symbol: str, expiration: str, puts_records: list, market_open: Optional[bool] = None) -> None:
    ttl = market_aware_ttl(OPTION_CHAIN_TTL_SEC, market_open) if market_open is not None else OPTION_CHAIN_TTL_SEC
    set_cached(f"chain:{symbol}:{expiration}", puts_records, ttl, market_open)


# --- Full screener result ---

def make_screener_cache_key(symbols: Optional[List[str]], overrides: Optional[Dict]) -> str:
    payload = {
        "symbols": sorted(symbols) if symbols else None,
        "overrides": overrides or {},
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]
    return f"screener:{digest}"


def get_screener_result_cached(cache_key: str, market_open: Optional[bool] = None) -> Optional[dict]:
    return get_cached(cache_key, SCREENER_RESULT_TTL_SEC, market_open)


def set_screener_result_cached(cache_key: str, result: dict, market_open: Optional[bool] = None) -> None:
    ttl = market_aware_ttl(SCREENER_RESULT_TTL_SEC, market_open) if market_open is not None else SCREENER_RESULT_TTL_SEC
    set_cached(cache_key, result, ttl, market_open)


# Back-compat aliases used elsewhere
def get_symbol_meta_cached(symbol: str) -> Optional[dict]:
    return get_cached(f"meta:{symbol}", INFO_TTL_SEC)


def set_symbol_meta_cached(symbol: str, meta: dict) -> None:
    set_cached(f"meta:{symbol}", meta, INFO_TTL_SEC)


def get_expirations_cached(symbol: str, min_dte: int, max_dte: int) -> Optional[list]:
    key = f"expiries:{symbol}:{min_dte}:{max_dte}"
    return get_cached(key, OPTION_CHAIN_TTL_SEC)


def set_expirations_cached(symbol: str, min_dte: int, max_dte: int, expirations: list) -> None:
    key = f"expiries:{symbol}:{min_dte}:{max_dte}"
    set_cached(key, expirations, OPTION_CHAIN_TTL_SEC)
