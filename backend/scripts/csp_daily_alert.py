#!/usr/bin/env python3
"""
Weekday CSP Alerts job (intended cron: 12:30 America/Chicago, Mon–Fri).

Usage (from backend/ with venv active):
  python scripts/csp_daily_alert.py
  python scripts/csp_daily_alert.py --user nileshrb --no-email
  python scripts/csp_daily_alert.py --mark-only

Env (SMTP):
  CSP_ALERTS_SMTP_HOST, CSP_ALERTS_SMTP_PORT, CSP_ALERTS_SMTP_USER,
  CSP_ALERTS_SMTP_PASSWORD, CSP_ALERTS_FROM_EMAIL
  CSP_ALERTS_SITE_URL  default https://maheshai.com
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CSP alerts] %(levelname)s %(message)s",
)
log = logging.getLogger("csp_daily_alert")


def main() -> int:
    parser = argparse.ArgumentParser(description="CSP daily alert scanner")
    parser.add_argument("--user", help="Only run for this user_id")
    parser.add_argument("--no-email", "--no-sms", action="store_true", dest="no_email",
                        help="Skip email send")
    parser.add_argument("--mark-only", action="store_true", help="Only mark/settle open ideas")
    parser.add_argument("--trigger", default="cron", help="trigger_source label")
    args = parser.parse_args()

    import csp_alerts_db as db
    import csp_alerts_service as svc

    db.init_db()

    if args.mark_only:
        settled = svc.settle_expired_ideas(args.user)
        marked = svc.mark_open_ideas(args.user)
        log.info("mark-only done settled=%s marked=%s", settled, marked)
        return 0

    if args.user:
        result = svc.run_daily_scan(
            args.user,
            trigger_source=args.trigger,
            send_email_alert=not args.no_email,
        )
        results = [result]
    else:
        for uid in svc.DEFAULT_ALERT_USERS:
            if svc.user_has_feature(uid):
                db.ensure_user_settings(uid)
        results = []
        users = set(svc.DEFAULT_ALERT_USERS) | set(db.list_all_alert_users())
        for uid in sorted(u for u in users if svc.user_has_feature(u)):
            results.append(
                svc.run_daily_scan(
                    uid,
                    trigger_source=args.trigger,
                    send_email_alert=not args.no_email,
                )
            )

    for r in results:
        log.info(
            "user=%s found=%s inserted=%s email=%s err=%s",
            r.get("user_id"),
            r.get("opportunities_found"),
            r.get("ideas_inserted"),
            r.get("email_sent"),
            r.get("error"),
        )
        if r.get("email_subject"):
            log.info("email_subject: %s", r["email_subject"])
    return 0 if all(not r.get("error") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
