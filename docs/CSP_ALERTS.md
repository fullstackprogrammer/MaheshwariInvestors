# CSP Alerts (SMS + paper P&L ledger)

Weekday scanner for a personal watchlist. Saves top opportunities, texts results (including zero hits), and tracks paper P/L until / after expiry.

## What it does

1. **Settings UI** (feature-gated; currently `nileshrb` only): phone, SMS on/off, ticker watchlist, scanner criteria.
2. **12:30 PM America/Chicago, Mon–Fri**: scan → store top N (default 3, one per ticker) → SMS → refresh open marks / settle expired.
3. **P&L table**: live unrealized = `(entry_premium − current put mid) × 100`; settled from underlying close vs strike at expiry.

Data lives in SQLite: `backend/data/csp_alerts.db` (gitignored via `*.db`).

## EC2 setup

### 1. Dependencies

```bash
cd /home/ec2-user/MaheshwariInvestors/backend
source venv/bin/activate
pip install -r requirements.txt   # includes boto3
```

### 2. AWS SNS for SMS

Option A — **direct SMS** (simplest): ensure the EC2 instance role (or `~/.aws` credentials) can `sns:Publish` to phone numbers. No topic needed.

Option B — **topic** (same pattern as backend-down alerts):

```bash
# create topic + SMS subscription once, then:
export CSP_ALERTS_SNS_TOPIC_ARN=arn:aws:sns:us-east-1:ACCOUNT:csp-alerts
```

Persist env for the API and cron, e.g. in the systemd unit:

```ini
Environment="CSP_ALERTS_SNS_TOPIC_ARN=arn:aws:sns:..."
Environment="CSP_ALERTS_SITE_URL=https://maheshai.com"
```

Then `sudo systemctl daemon-reload && sudo systemctl restart maheshwari-api`.

### 3. Cron (weekdays 12:30 CT)

```bash
sudo crontab -u ec2-user -e
```

Add:

```cron
CRON_TZ=America/Chicago
30 12 * * 1-5  cd /home/ec2-user/MaheshwariInvestors/backend && ./venv/bin/python scripts/csp_daily_alert.py >> /home/ec2-user/csp_alerts.log 2>&1
```

Optional EOD mark/settle (e.g. 4:15 PM CT):

```cron
15 16 * * 1-5  cd /home/ec2-user/MaheshwariInvestors/backend && ./venv/bin/python scripts/csp_daily_alert.py --mark-only >> /home/ec2-user/csp_alerts.log 2>&1
```

### 4. Manual test

```bash
cd /home/ec2-user/MaheshwariInvestors/backend
source venv/bin/activate
# Save phone via UI first, or:
python -c "import csp_alerts_db as d; d.init_db(); d.ensure_user_settings('nileshrb'); d.update_user_settings('nileshrb', phone='7324216751')"
python scripts/csp_daily_alert.py --user nileshrb
# Dry run without SMS:
python scripts/csp_daily_alert.py --user nileshrb --no-sms
```

## Opening the feature to more users later

In `csp_alerts_service.py`:

```python
FEATURE_USERS = {"nileshrb", "mai108"}  # add ids
DEFAULT_ALERT_USERS = ["nileshrb", "mai108"]
```

Each user has their own settings row and ideas. Frontend gate is `userId` ∈ feature set (same list conceptually).

## API

| Method | Path | Notes |
|--------|------|--------|
| GET | `/csp-alerts/settings?user_id=` | |
| PUT | `/csp-alerts/settings?user_id=` | body: phone, sms_enabled, watchlist, criteria |
| GET | `/csp-alerts/ideas?user_id=&refresh=1` | ledger + summary |
| POST | `/csp-alerts/run?user_id=&send_sms=true` | manual scan (slow) |
