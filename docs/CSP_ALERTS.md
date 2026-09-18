# CSP Alerts (email + paper P&L ledger)

Weekday scanner for a personal watchlist. Saves top opportunities, emails results (including zero hits), and tracks paper P/L until / after expiry.

## What it does

1. **Settings UI** (feature-gated; currently `nileshrb` only): email, email on/off, ticker watchlist, scanner criteria.
2. **12:30 PM America/Chicago, Mon–Fri**: scan → store top N (default 3, one per ticker) → email → refresh open marks / settle expired.
3. **P&L table**: live unrealized = `(entry_premium − current put mid) × 100`; settled from underlying close vs strike at expiry.

Data lives in SQLite: `backend/data/csp_alerts.db` (gitignored via `*.db`).

## Email via SMTP (recommended)

No AWS SNS / toll-free number needed. Use Gmail (app password), Outlook, or Amazon SES SMTP.

### 1. Create a Gmail app password (example)

1. Google Account → Security → 2-Step Verification (on)
2. App passwords → generate one for “Mail”
3. Use that 16-char password (not your normal Gmail password)

### 2. Set env on EC2 (API + cron)

```bash
sudo systemctl edit maheshwari-api
```

```ini
[Service]
Environment="CSP_ALERTS_SMTP_HOST=smtp.gmail.com"
Environment="CSP_ALERTS_SMTP_PORT=587"
Environment="CSP_ALERTS_SMTP_USER=youraddress@gmail.com"
Environment="CSP_ALERTS_SMTP_PASSWORD=xxxx xxxx xxxx xxxx"
Environment="CSP_ALERTS_FROM_EMAIL=youraddress@gmail.com"
Environment="CSP_ALERTS_SITE_URL=https://maheshai.com"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart maheshwari-api
```

Remove any old `CSP_ALERTS_SNS_TOPIC_ARN` line — it is unused now.

### 3. Cron (include the same SMTP env)

```cron
CRON_TZ=America/Chicago
30 12 * * 1-5  cd /home/ec2-user/MaheshwariInvestors/backend && CSP_ALERTS_SMTP_HOST=smtp.gmail.com CSP_ALERTS_SMTP_PORT=587 CSP_ALERTS_SMTP_USER=youraddress@gmail.com CSP_ALERTS_SMTP_PASSWORD='your-app-password' CSP_ALERTS_FROM_EMAIL=youraddress@gmail.com CSP_ALERTS_SITE_URL=https://maheshai.com ./venv/bin/python scripts/csp_daily_alert.py >> /home/ec2-user/csp_alerts.log 2>&1
```

Or use a wrapper script that `export`s those vars (cleaner than putting the password in crontab).

Optional EOD mark/settle:

```cron
15 16 * * 1-5  cd /home/ec2-user/MaheshwariInvestors/backend && ./venv/bin/python scripts/csp_daily_alert.py --mark-only >> /home/ec2-user/csp_alerts.log 2>&1
```

### 4. UI

1. Log in as **nileshrb** → **CSP Alerts**
2. Enter your alert email → enable send → Save
3. **Run scan (no email)** then **Run scan now + email**

### 5. Manual CLI test

```bash
cd /home/ec2-user/MaheshwariInvestors/backend
source venv/bin/activate
export CSP_ALERTS_SMTP_HOST=smtp.gmail.com
export CSP_ALERTS_SMTP_PORT=587
export CSP_ALERTS_SMTP_USER=youraddress@gmail.com
export CSP_ALERTS_SMTP_PASSWORD='your-app-password'
export CSP_ALERTS_FROM_EMAIL=youraddress@gmail.com
python scripts/csp_daily_alert.py --user nileshrb
```

## Opening the feature to more users later

In `csp_alerts_service.py`:

```python
FEATURE_USERS = {"nileshrb", "mai108"}
DEFAULT_ALERT_USERS = ["nileshrb", "mai108"]
```

And add the matching user id to `CSP_ALERTS_USERS` in `frontend/src/App.jsx`.

## API

| Method | Path | Notes |
|--------|------|--------|
| GET | `/csp-alerts/settings?user_id=` | |
| PUT | `/csp-alerts/settings?user_id=` | body: email, email_enabled, watchlist, criteria |
| GET | `/csp-alerts/ideas?user_id=&refresh=1` | ledger + summary |
| POST | `/csp-alerts/run?user_id=&send_email=true` | manual scan (slow) |
