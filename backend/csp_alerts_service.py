"""
CSP Alerts business logic: scan → persist top N → SMS → mark/settle P&L.

Feature access is gated by FEATURE_USERS (currently nileshrb only).
Settings/ideas are keyed by user_id so more users can be enabled later.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf

import csp_alerts_db as db
from csp_screener import run_screener

log = logging.getLogger(__name__)

# Who may use CSP Alerts UI/API today. Add user ids here to open the feature later.
FEATURE_USERS = {"nileshrb"}

# Cron should process these users even if they have not opened the UI yet.
DEFAULT_ALERT_USERS = ["nileshrb"]

SNS_TOPIC_ARN_ENV = "CSP_ALERTS_SNS_TOPIC_ARN"
SITE_URL_ENV = "CSP_ALERTS_SITE_URL"
DEFAULT_SITE_URL = "https://maheshai.com"


def user_has_feature(user_id: str) -> bool:
    return (user_id or "").strip().lower() in FEATURE_USERS


def require_feature_user(user_id: str) -> str:
    uid = (user_id or "").strip().lower()
    if not uid:
        raise ValueError("user_id is required")
    if not user_has_feature(uid):
        raise PermissionError("CSP Alerts is not enabled for this user")
    return uid


def get_settings(user_id: str) -> Dict[str, Any]:
    uid = require_feature_user(user_id)
    return db.ensure_user_settings(uid)


def save_settings(user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    uid = require_feature_user(user_id)
    phone = payload.get("phone")
    if phone is not None:
        phone = _normalize_phone(str(phone))
    watchlist = payload.get("watchlist")
    if isinstance(watchlist, str):
        watchlist = [p.strip() for p in re.split(r"[\s,;]+", watchlist) if p.strip()]
    return db.update_user_settings(
        uid,
        phone=phone,
        sms_enabled=payload.get("sms_enabled"),
        watchlist=watchlist,
        criteria=payload.get("criteria"),
    )


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if digits and len(digits) != 10:
        raise ValueError("Phone must be a 10-digit US number")
    return digits


def _criteria_to_overrides(criteria: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "min_dte", "max_dte", "put_delta_min", "put_delta_max", "max_bid_ask_pct",
        "min_annualized_return_pct", "min_open_interest", "min_option_volume",
        "max_price_vs_ma200_pct", "min_iv_rank", "skip_earnings",
    ]
    overrides = {k: criteria[k] for k in keys if k in criteria}
    # Custom ticker list: skip market-cap / analyst-upside gates that need broad universe
    overrides["max_results"] = 50
    overrides["max_symbols"] = max(len(criteria.get("watchlist") or []), 11)
    return overrides


def unrealized_pnl(entry_premium: float, current_put_mid: Optional[float]) -> Optional[float]:
    if current_put_mid is None or entry_premium is None:
        return None
    return round((float(entry_premium) - float(current_put_mid)) * 100.0, 2)


def settled_pnl(entry_premium: float, strike: float, stock_close: float) -> Tuple[float, str]:
    """Short put settlement P/L for 1 contract."""
    prem = float(entry_premium)
    k = float(strike)
    s = float(stock_close)
    if s >= k:
        return round(prem * 100.0, 2), "expired_otm"
    return round((prem - (k - s)) * 100.0, 2), "expired_itm"


def _fetch_put_mid(ticker: str, expiration: str, strike: float) -> Optional[float]:
    try:
        t = yf.Ticker(ticker)
        chain = t.option_chain(expiration)
        puts = getattr(chain, "puts", None)
        if puts is None or puts.empty:
            return None
        row = puts.loc[(puts["strike"] - strike).abs() < 0.011]
        if row.empty:
            return None
        r = row.iloc[0]
        bid = float(r["bid"]) if r.get("bid") == r.get("bid") and r.get("bid") is not None else 0.0
        ask = float(r["ask"]) if r.get("ask") == r.get("ask") and r.get("ask") is not None else 0.0
        last = float(r["lastPrice"]) if r.get("lastPrice") == r.get("lastPrice") else None
        if bid > 0 and ask > 0:
            return round((bid + ask) / 2.0, 4)
        if bid > 0:
            return round(bid, 4)
        if ask > 0:
            return round(ask, 4)
        return round(last, 4) if last else None
    except Exception as e:
        log.warning("[CSP alerts] put mid fetch failed %s %s %.2f: %s", ticker, expiration, strike, e)
        return None


def _fetch_spot(ticker: str) -> Optional[float]:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        px = info.get("currentPrice") or info.get("regularMarketPrice")
        if px:
            return float(px)
        hist = t.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        log.warning("[CSP alerts] spot fetch failed %s: %s", ticker, e)
    return None


def _fetch_expiry_close(ticker: str, expiration: str) -> Optional[float]:
    """Underlying close on (or nearest prior to) option expiration date."""
    try:
        exp = datetime.strptime(expiration, "%Y-%m-%d")
        start = (exp - timedelta(days=5)).strftime("%Y-%m-%d")
        end = (exp + timedelta(days=2)).strftime("%Y-%m-%d")
        t = yf.Ticker(ticker)
        hist = t.history(start=start, end=end)
        if hist is None or hist.empty:
            return None
        # Normalize index to dates
        closes = hist["Close"]
        target = exp.date()
        for idx in reversed(list(closes.index)):
            d = idx.date() if hasattr(idx, "date") else idx
            if d <= target:
                return float(closes.loc[idx])
        return float(closes.iloc[-1])
    except Exception as e:
        log.warning("[CSP alerts] expiry close failed %s %s: %s", ticker, expiration, e)
        return None


def mark_open_ideas(user_id: Optional[str] = None) -> int:
    """Refresh live marks for open ideas. Returns count updated."""
    ideas = db.list_open_ideas(user_id)
    updated = 0
    today = datetime.now().date()
    for idea in ideas:
        exp = datetime.strptime(idea["expiration"], "%Y-%m-%d").date()
        if exp < today:
            # Leave for settle_expired_ideas
            continue
        spot = _fetch_spot(idea["ticker"])
        mid = _fetch_put_mid(idea["ticker"], idea["expiration"], idea["put_strike"])
        pnl = unrealized_pnl(idea["entry_premium"], mid)
        db.update_idea_mark(
            idea["id"],
            last_spot=spot,
            last_put_mid=mid,
            last_unrealized_pnl=pnl,
        )
        updated += 1
    return updated


def settle_expired_ideas(user_id: Optional[str] = None) -> int:
    """Settle open ideas whose expiration date has passed (use expiry close)."""
    ideas = db.list_open_ideas(user_id)
    today = datetime.now().date()
    settled = 0
    for idea in ideas:
        exp = datetime.strptime(idea["expiration"], "%Y-%m-%d").date()
        if exp >= today:
            continue
        close_px = _fetch_expiry_close(idea["ticker"], idea["expiration"])
        if close_px is None:
            close_px = _fetch_spot(idea["ticker"])
        if close_px is None:
            log.warning("[CSP alerts] cannot settle idea %s — no close", idea["id"])
            continue
        pnl, status = settled_pnl(idea["entry_premium"], idea["put_strike"], close_px)
        db.settle_idea(
            idea["id"],
            settled_stock_close=close_px,
            settled_pnl=pnl,
            settled_status=status,
        )
        settled += 1
    return settled


def format_sms(
    user_id: str,
    opportunities: List[Dict[str, Any]],
    *,
    top_n: int,
) -> str:
    site = os.environ.get(SITE_URL_ENV, DEFAULT_SITE_URL).rstrip("/")
    try:
        from zoneinfo import ZoneInfo
        stamp = datetime.now(ZoneInfo("America/Chicago")).strftime("%m/%d %H:%M CT")
    except Exception:
        stamp = datetime.now().strftime("%m/%d %H:%M")
    if not opportunities:
        return f"CSP alert {stamp}: 0 opportunities on your watchlist. {site}"
    parts = []
    for o in opportunities[:top_n]:
        t = o.get("ticker")
        k = o.get("put_strike")
        exp = (o.get("expiration") or "")[5:]  # MM-DD
        score = o.get("composite_score")
        ann = o.get("annualized_return_pct")
        parts.append(f"{t} ${k:g}p {exp} sc{score} ann{ann}%")
    body = f"CSP {stamp}: " + " | ".join(parts)
    extra = len(opportunities) - top_n
    if extra > 0:
        body += f" | +{extra} more"
    body += f" {site}"
    # SMS soft limit ~320 for concatenated; keep under ~300
    return body[:300]


def send_sms(phone: str, message: str) -> bool:
    """Publish SMS via AWS SNS. Uses CSP_ALERTS_SNS_TOPIC_ARN if set; else direct SMS publish."""
    if not phone:
        log.warning("[CSP alerts] SMS skipped — no phone")
        return False
    e164 = f"+1{phone}" if not phone.startswith("+") else phone
    topic = os.environ.get(SNS_TOPIC_ARN_ENV, "").strip()
    try:
        import boto3
        client = boto3.client("sns")
        if topic:
            client.publish(TopicArn=topic, Message=message)
        else:
            client.publish(PhoneNumber=e164, Message=message)
        log.info("[CSP alerts] SMS sent to %s (%d chars)", e164[-4:].rjust(4, "*"), len(message))
        return True
    except Exception as e:
        log.error("[CSP alerts] SMS failed: %s", e)
        return False


def run_daily_scan(
    user_id: str,
    *,
    trigger_source: str = "cron",
    send_sms_alert: bool = True,
    refresh_marks: bool = True,
) -> Dict[str, Any]:
    """
    Full pipeline for one user: settle expired → scan watchlist → persist top N → SMS → mark opens.
    Always attempts SMS when enabled (including zero results).
    """
    uid = require_feature_user(user_id)
    settings = db.ensure_user_settings(uid)
    watchlist = settings["watchlist"] or list(db.DEFAULT_WATCHLIST)
    criteria = settings["criteria"]
    top_n = int(criteria.get("top_n") or 3)

    error = None
    opportunities: List[Dict[str, Any]] = []
    top: List[Dict[str, Any]] = []
    inserted = 0
    sms_sent = False
    sms_body = None
    run_id = None

    try:
        settle_expired_ideas(uid)
        overrides = _criteria_to_overrides(criteria)
        # Custom symbols: skip MA200 filter noise for ETFs by not applying sector/universe gates
        # run_screener already treats custom_symbols specially
        result = run_screener(
            symbols=watchlist,
            max_results=50,
            overrides=overrides,
            community_weights=None,
            stock_cache_snapshot=None,
        )
        opportunities = result.get("opportunities") or []
        # Sort already by composite_score; take top_n unique tickers preferring best score
        top = _select_top(opportunities, top_n)

        # Create run first so ideas can reference run_id
        run_id = db.create_scan_run(
            uid,
            symbols_scanned=len(watchlist),
            opportunities_found=len(opportunities),
            ideas_inserted=0,
            sms_sent=False,
            sms_body=None,
            error=None,
            trigger_source=trigger_source,
        )
        for opp in top:
            if db.upsert_tracked_idea(uid, run_id, opp):
                inserted += 1

        sms_body = format_sms(uid, top, top_n=top_n)
        if send_sms_alert and settings.get("sms_enabled") and settings.get("phone"):
            sms_sent = send_sms(settings["phone"], sms_body)
        elif send_sms_alert and settings.get("sms_enabled") and not settings.get("phone"):
            log.warning("[CSP alerts] SMS enabled but phone empty for %s", uid)

        if refresh_marks:
            mark_open_ideas(uid)

        # Update run row with final SMS/insert counts (create a replacement note via new fields)
        # Simplest: insert a corrected summary by updating — add update helper inline
        _update_scan_run(run_id, ideas_inserted=inserted, sms_sent=sms_sent, sms_body=sms_body)

    except Exception as e:
        error = str(e)
        log.exception("[CSP alerts] scan failed for %s", uid)
        if run_id is None:
            run_id = db.create_scan_run(
                uid,
                symbols_scanned=len(watchlist),
                opportunities_found=0,
                ideas_inserted=0,
                sms_sent=False,
                sms_body=None,
                error=error,
                trigger_source=trigger_source,
            )
        if send_sms_alert and settings.get("sms_enabled") and settings.get("phone"):
            sms_body = f"CSP alert FAILED: {error[:180]}"
            sms_sent = send_sms(settings["phone"], sms_body)
            _update_scan_run(run_id, ideas_inserted=0, sms_sent=sms_sent, sms_body=sms_body, error=error)

    return {
        "user_id": uid,
        "run_id": run_id,
        "watchlist": watchlist,
        "opportunities_found": len(opportunities),
        "top": top,
        "ideas_inserted": inserted,
        "sms_sent": sms_sent,
        "sms_body": sms_body,
        "error": error,
    }


def _select_top(opportunities: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """Prefer diversity: at most one idea per ticker, then fill."""
    picked: List[Dict[str, Any]] = []
    seen = set()
    for o in opportunities:
        t = (o.get("ticker") or "").upper()
        if t in seen:
            continue
        seen.add(t)
        picked.append(o)
        if len(picked) >= top_n:
            break
    return picked


def _update_scan_run(
    run_id: int,
    *,
    ideas_inserted: int,
    sms_sent: bool,
    sms_body: Optional[str],
    error: Optional[str] = None,
) -> None:
    with db._lock:
        conn = db._connect()
        try:
            conn.execute(
                """
                UPDATE csp_scan_runs
                SET ideas_inserted = ?, sms_sent = ?, sms_body = ?,
                    error = COALESCE(?, error)
                WHERE id = ?
                """,
                (ideas_inserted, 1 if sms_sent else 0, sms_body, error, run_id),
            )
            conn.commit()
        finally:
            conn.close()


def list_ideas_for_user(
    user_id: str,
    *,
    status: Optional[str] = None,
    refresh: bool = False,
) -> Dict[str, Any]:
    uid = require_feature_user(user_id)
    if refresh:
        settle_expired_ideas(uid)
        mark_open_ideas(uid)
    ideas = db.list_ideas(uid, status=status)
    open_pnl = sum((i["last_unrealized_pnl"] or 0) for i in ideas if i["status"] == "open")
    settled_pnl_total = sum((i["settled_pnl"] or 0) for i in ideas if i["status"] == "settled")
    settled = [i for i in ideas if i["status"] == "settled"]
    wins = sum(1 for i in settled if (i["settled_pnl"] or 0) > 0)
    return {
        "ideas": ideas,
        "summary": {
            "open_count": sum(1 for i in ideas if i["status"] == "open"),
            "settled_count": len(settled),
            "open_unrealized_pnl": round(open_pnl, 2),
            "settled_realized_pnl": round(settled_pnl_total, 2),
            "settled_win_rate": round(wins / len(settled), 3) if settled else None,
        },
        "latest_run": db.latest_run(uid),
    }


def run_for_all_configured_users(*, trigger_source: str = "cron") -> List[Dict[str, Any]]:
    """
    Cron entry: ensure default users exist, then scan every FEATURE user with settings
    (or at least DEFAULT_ALERT_USERS).
    """
    results = []
    users = set(DEFAULT_ALERT_USERS) | set(db.list_all_alert_users())
    users = {u for u in users if user_has_feature(u)}
    for uid in sorted(users):
        db.ensure_user_settings(uid)
        results.append(run_daily_scan(uid, trigger_source=trigger_source))
    return results
