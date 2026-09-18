"""
SQLite persistence for CSP Alerts (per-user settings + tracked paper ideas).

Designed for multi-user later: every row is keyed by user_id.
Feature gate (who can use the UI/API) lives in csp_alerts_service.FEATURE_USERS.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "data" / "csp_alerts.db"

_lock = threading.Lock()

DEFAULT_WATCHLIST = [
    "MU", "SLV", "CRWD", "SPCX", "TQQQ", "AVGO", "SNDK", "TSM", "AMD", "UAL", "MSFT",
]

DEFAULT_CRITERIA = {
    "min_dte": 7,
    "max_dte": 30,
    "put_delta_min": -0.30,
    "put_delta_max": -0.10,
    "max_bid_ask_pct": 0.10,
    "min_annualized_return_pct": 0.10,
    "min_open_interest": 100,
    "min_option_volume": 10,
    "max_price_vs_ma200_pct": 1.10,
    "min_iv_rank": 0,
    "skip_earnings": True,
    "top_n": 3,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS csp_alert_settings (
                    user_id TEXT PRIMARY KEY,
                    phone TEXT NOT NULL DEFAULT '',
                    sms_enabled INTEGER NOT NULL DEFAULT 1,
                    watchlist_json TEXT NOT NULL,
                    criteria_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS csp_scan_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    ran_at TEXT NOT NULL,
                    symbols_scanned INTEGER NOT NULL DEFAULT 0,
                    opportunities_found INTEGER NOT NULL DEFAULT 0,
                    ideas_inserted INTEGER NOT NULL DEFAULT 0,
                    sms_sent INTEGER NOT NULL DEFAULT 0,
                    sms_body TEXT,
                    error TEXT,
                    trigger_source TEXT NOT NULL DEFAULT 'cron'
                );

                CREATE TABLE IF NOT EXISTS csp_tracked_ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    run_id INTEGER,
                    suggested_at TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    put_strike REAL NOT NULL,
                    expiration TEXT NOT NULL,
                    entry_premium REAL NOT NULL,
                    entry_spot REAL,
                    entry_score REAL,
                    entry_ann_return_pct REAL,
                    entry_delta REAL,
                    entry_dte INTEGER,
                    status TEXT NOT NULL DEFAULT 'open',
                    last_spot REAL,
                    last_put_mid REAL,
                    last_unrealized_pnl REAL,
                    marked_at TEXT,
                    settled_stock_close REAL,
                    settled_pnl REAL,
                    settled_status TEXT,
                    settled_at TEXT,
                    UNIQUE(user_id, ticker, put_strike, expiration)
                );

                CREATE INDEX IF NOT EXISTS idx_ideas_user_status
                    ON csp_tracked_ideas(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_ideas_expiration
                    ON csp_tracked_ideas(expiration);
                CREATE INDEX IF NOT EXISTS idx_runs_user
                    ON csp_scan_runs(user_id, ran_at);
                """
            )
            conn.commit()
        finally:
            conn.close()


def ensure_user_settings(user_id: str) -> Dict[str, Any]:
    """Return settings for user_id, creating defaults if missing."""
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM csp_alert_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return _settings_row_to_dict(row)
            now = _utc_now_iso()
            conn.execute(
                """
                INSERT INTO csp_alert_settings
                    (user_id, phone, sms_enabled, watchlist_json, criteria_json, updated_at)
                VALUES (?, '', 1, ?, ?, ?)
                """,
                (
                    user_id,
                    json.dumps(DEFAULT_WATCHLIST),
                    json.dumps(DEFAULT_CRITERIA),
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM csp_alert_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
            return _settings_row_to_dict(row)
        finally:
            conn.close()


def _settings_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    watchlist = json.loads(row["watchlist_json"] or "[]")
    criteria = {**DEFAULT_CRITERIA, **json.loads(row["criteria_json"] or "{}")}
    return {
        "user_id": row["user_id"],
        "phone": row["phone"] or "",
        "sms_enabled": bool(row["sms_enabled"]),
        "watchlist": watchlist,
        "criteria": criteria,
        "updated_at": row["updated_at"],
    }


def update_user_settings(
    user_id: str,
    *,
    phone: Optional[str] = None,
    sms_enabled: Optional[bool] = None,
    watchlist: Optional[List[str]] = None,
    criteria: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    current = ensure_user_settings(user_id)
    new_phone = current["phone"] if phone is None else str(phone).strip()
    new_sms = current["sms_enabled"] if sms_enabled is None else bool(sms_enabled)
    if watchlist is None:
        new_watch = current["watchlist"]
    else:
        new_watch = _normalize_watchlist(watchlist)
    if criteria is None:
        new_crit = current["criteria"]
    else:
        new_crit = {**DEFAULT_CRITERIA, **criteria}
        if "top_n" in new_crit:
            new_crit["top_n"] = max(1, min(int(new_crit["top_n"]), 10))

    now = _utc_now_iso()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE csp_alert_settings
                SET phone = ?, sms_enabled = ?, watchlist_json = ?,
                    criteria_json = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    new_phone,
                    1 if new_sms else 0,
                    json.dumps(new_watch),
                    json.dumps(new_crit),
                    now,
                    user_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return ensure_user_settings(user_id)


def _normalize_watchlist(raw: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in raw:
        t = (item or "").strip().upper()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:50]


def list_users_with_sms() -> List[str]:
    """Users who have SMS enabled and a phone number (for cron)."""
    init_db()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT user_id FROM csp_alert_settings
                WHERE sms_enabled = 1 AND TRIM(phone) != ''
                """
            ).fetchall()
            return [r["user_id"] for r in rows]
        finally:
            conn.close()


def list_all_alert_users() -> List[str]:
    init_db()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute("SELECT user_id FROM csp_alert_settings").fetchall()
            return [r["user_id"] for r in rows]
        finally:
            conn.close()


def create_scan_run(
    user_id: str,
    *,
    symbols_scanned: int,
    opportunities_found: int,
    ideas_inserted: int,
    sms_sent: bool,
    sms_body: Optional[str],
    error: Optional[str],
    trigger_source: str,
) -> int:
    init_db()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO csp_scan_runs
                    (user_id, ran_at, symbols_scanned, opportunities_found,
                     ideas_inserted, sms_sent, sms_body, error, trigger_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    _utc_now_iso(),
                    symbols_scanned,
                    opportunities_found,
                    ideas_inserted,
                    1 if sms_sent else 0,
                    sms_body,
                    error,
                    trigger_source,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()


def upsert_tracked_idea(
    user_id: str,
    run_id: Optional[int],
    opp: Dict[str, Any],
) -> bool:
    """
    Insert a new open idea, or refresh suggested_at if same contract already open.
    Returns True if a new row was inserted.
    """
    init_db()
    ticker = (opp.get("ticker") or "").upper()
    strike = float(opp["put_strike"])
    expiration = opp["expiration"]
    premium = float(opp.get("premium_received") or opp.get("bid") or 0)
    now = _utc_now_iso()
    with _lock:
        conn = _connect()
        try:
            existing = conn.execute(
                """
                SELECT id, status FROM csp_tracked_ideas
                WHERE user_id = ? AND ticker = ? AND put_strike = ? AND expiration = ?
                """,
                (user_id, ticker, strike, expiration),
            ).fetchone()
            if existing:
                if existing["status"] == "open":
                    conn.execute(
                        """
                        UPDATE csp_tracked_ideas
                        SET suggested_at = ?, run_id = ?,
                            entry_score = COALESCE(?, entry_score),
                            entry_ann_return_pct = COALESCE(?, entry_ann_return_pct)
                        WHERE id = ?
                        """,
                        (
                            now,
                            run_id,
                            opp.get("composite_score"),
                            opp.get("annualized_return_pct"),
                            existing["id"],
                        ),
                    )
                    conn.commit()
                    return False
                # Already settled same contract — leave historical row alone
                return False

            conn.execute(
                """
                INSERT INTO csp_tracked_ideas
                    (user_id, run_id, suggested_at, ticker, put_strike, expiration,
                     entry_premium, entry_spot, entry_score, entry_ann_return_pct,
                     entry_delta, entry_dte, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    user_id,
                    run_id,
                    now,
                    ticker,
                    strike,
                    expiration,
                    premium,
                    opp.get("current_stock_price"),
                    opp.get("composite_score"),
                    opp.get("annualized_return_pct"),
                    opp.get("delta"),
                    opp.get("dte"),
                ),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def list_ideas(
    user_id: str,
    *,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    init_db()
    with _lock:
        conn = _connect()
        try:
            if status in ("open", "settled"):
                rows = conn.execute(
                    """
                    SELECT * FROM csp_tracked_ideas
                    WHERE user_id = ? AND status = ?
                    ORDER BY suggested_at DESC
                    LIMIT ?
                    """,
                    (user_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM csp_tracked_ideas
                    WHERE user_id = ?
                    ORDER BY
                        CASE status WHEN 'open' THEN 0 ELSE 1 END,
                        suggested_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()
            return [_idea_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def list_open_ideas(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    init_db()
    with _lock:
        conn = _connect()
        try:
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM csp_tracked_ideas WHERE status = 'open' AND user_id = ?",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM csp_tracked_ideas WHERE status = 'open'"
                ).fetchall()
            return [_idea_row_to_dict(r) for r in rows]
        finally:
            conn.close()


def update_idea_mark(
    idea_id: int,
    *,
    last_spot: Optional[float],
    last_put_mid: Optional[float],
    last_unrealized_pnl: Optional[float],
) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE csp_tracked_ideas
                SET last_spot = ?, last_put_mid = ?, last_unrealized_pnl = ?, marked_at = ?
                WHERE id = ?
                """,
                (last_spot, last_put_mid, last_unrealized_pnl, _utc_now_iso(), idea_id),
            )
            conn.commit()
        finally:
            conn.close()


def settle_idea(
    idea_id: int,
    *,
    settled_stock_close: float,
    settled_pnl: float,
    settled_status: str,
) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE csp_tracked_ideas
                SET status = 'settled',
                    settled_stock_close = ?,
                    settled_pnl = ?,
                    settled_status = ?,
                    settled_at = ?,
                    last_unrealized_pnl = ?,
                    last_spot = ?,
                    marked_at = ?
                WHERE id = ?
                """,
                (
                    settled_stock_close,
                    settled_pnl,
                    settled_status,
                    _utc_now_iso(),
                    settled_pnl,
                    settled_stock_close,
                    _utc_now_iso(),
                    idea_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def latest_run(user_id: str) -> Optional[Dict[str, Any]]:
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM csp_scan_runs
                WHERE user_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()


def _idea_row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "run_id": row["run_id"],
        "suggested_at": row["suggested_at"],
        "ticker": row["ticker"],
        "put_strike": row["put_strike"],
        "expiration": row["expiration"],
        "entry_premium": row["entry_premium"],
        "entry_spot": row["entry_spot"],
        "entry_score": row["entry_score"],
        "entry_ann_return_pct": row["entry_ann_return_pct"],
        "entry_delta": row["entry_delta"],
        "entry_dte": row["entry_dte"],
        "status": row["status"],
        "last_spot": row["last_spot"],
        "last_put_mid": row["last_put_mid"],
        "last_unrealized_pnl": row["last_unrealized_pnl"],
        "marked_at": row["marked_at"],
        "settled_stock_close": row["settled_stock_close"],
        "settled_pnl": row["settled_pnl"],
        "settled_status": row["settled_status"],
        "settled_at": row["settled_at"],
    }
