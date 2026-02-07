# SMS Alert When Backend API Stops Responding

Get a text message to your phone when the backend (e.g. `https://maheshai.com/api`) stops responding. Two options: **AWS (SNS + Lambda)** or a **free external monitor**.

---

## Option 1: AWS SNS + Lambda (recommended)

A scheduled Lambda runs every 5 minutes, checks your API health endpoint, and sends an SMS via SNS if the check fails.

### Automated deploy (script)

From the project root, run one of these (replace with your 10-digit phone number):

**Bash (Linux / Mac / Git Bash):**
```bash
cd deploy/backend-alert
./deploy.sh 7324216751
```

**PowerShell (Windows):**
```powershell
cd deploy\backend-alert
.\deploy.ps1 -Phone 7324216751
```

The script creates the SNS topic, SMS subscription, Lambda function, and EventBridge rule (every 5 min). See **[deploy/backend-alert/README.md](../deploy/backend-alert/README.md)** for options (health URL, region) and how to remove resources.

---

### Manual setup (Console)

If you prefer to create resources in the AWS Console:

#### 1. Create an SNS topic and subscribe your phone

1. In **AWS Console** go to **SNS** → **Topics** → **Create topic**.
   - Type: **Standard**
   - Name: `backend-down-alerts`
   - Create topic.

2. **Create subscription** on that topic:
   - **Protocol:** SMS
   - **Endpoint:** your 10-digit US number, e.g. `7324216751` (no +1 in console is OK; SNS accepts it)
   - Create subscription.
   - Confirm the subscription when you receive the test SMS (if prompted).

3. Note the **Topic ARN** (e.g. `arn:aws:sns:us-east-1:123456789012:backend-down-alerts`).

### 2. Create the Lambda function

1. **Lambda** → **Create function**:
   - Name: `backend-health-check`
   - Runtime: **Python 3.12**
   - Create function.

2. In the function, open the **Code** tab and replace the default code with:

```python
import urllib.request
import json
import os

# Set these in Lambda environment variables (Configuration → Environment variables)
HEALTH_URL = os.environ.get("HEALTH_URL", "https://maheshai.com/api/health")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
TIMEOUT_SEC = 10

def lambda_handler(event, context):
    if not SNS_TOPIC_ARN:
        return {"statusCode": 500, "body": "SNS_TOPIC_ARN not set"}
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as r:
            if r.status != 200:
                send_alert(f"Backend returned status {r.status}")
                return {"statusCode": 200, "body": "Alert sent"}
    except Exception as e:
        send_alert(f"Backend unreachable: {e}")
        return {"statusCode": 200, "body": "Alert sent"}
    return {"statusCode": 200, "body": "OK"}

def send_alert(message):
    import boto3
    sns = boto3.client("sns")
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="MAI Backend Down",
        Message=f"MAI backend is not responding. {message}",
    )
```

3. **Environment variables** (Configuration → Environment variables → Edit):
   - `HEALTH_URL` = `https://maheshai.com/api/health` (or your API health URL)
   - `SNS_TOPIC_ARN` = the Topic ARN from step 1 (e.g. `arn:aws:sns:us-east-1:123456789012:backend-down-alerts`)

4. **Permissions:** Lambda needs permission to publish to SNS.
   - Configuration → Permissions → click the **role name** (opens IAM).
   - Add permission → Create inline policy → JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:backend-down-alerts"
    }
  ]
}
```

   Replace `YOUR_ACCOUNT_ID` and the topic name if different. Save.

### 3. Schedule the Lambda (EventBridge)

1. In the Lambda function, go to **Add trigger**.
2. Select **EventBridge (CloudWatch Events)**.
3. Create a new rule:
   - **Rule name:** `backend-health-every-5min`
   - **Rule type:** Schedule expression
   - **Schedule expression:** `rate(5 minutes)`
4. Add the trigger.

Lambda will run every 5 minutes. If `https://maheshai.com/api/health` fails (timeout or non-200), it publishes to SNS and you get an SMS.

**SMS costs:** AWS SNS charges a small amount per SMS (see AWS SNS pricing). Lambda and EventBridge have a generous free tier.

---

## Option 2: Free external uptime monitor

Use a service that pings your URL and sends alerts:

- **UptimeRobot** (uptimerobot.com) – Free tier: monitors every 5 min, alerts by email/SMS (SMS may require paid plan or integration).
- **Better Uptime** (betteruptime.com) – Free tier, incident alerts by email/Slack; SMS often via paid plan or Zapier.

Setup is usually: add a monitor for `https://maheshai.com/api/health`, set check interval (e.g. 5 min), and add your phone for SMS if the plan supports it. If only email is free, you can use your carrier’s **email-to-SMS** (e.g. `7324216751@vtext.com` for Verizon) so alerts still arrive as text.

---

## Quick reference (Option 1)

| Item        | Value |
|------------|--------|
| Health URL | `https://maheshai.com/api/health` |
| Lambda env | `HEALTH_URL`, `SNS_TOPIC_ARN` |
| Schedule   | `rate(5 minutes)` |
| SMS        | SNS topic subscription = your phone number |
