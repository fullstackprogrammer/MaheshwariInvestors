# Backend health-check alert (SNS + Lambda + EventBridge)

Sends an SMS to your phone when the backend API stops responding. Runs a Lambda every 5 minutes; if the health check fails, Lambda publishes to SNS and you get a text.

## Prerequisites

- **AWS CLI** installed and configured (`aws configure` with credentials and region).
- **Bash** (for `deploy.sh`) or **PowerShell** (for `deploy.ps1`). On Windows you can use Git Bash for `deploy.sh`.
- **IAM permissions:** The IAM user (e.g. `maheshai`) running the script must be allowed to create SNS topics, IAM roles, Lambda functions, and EventBridge rules. If you see "Access Denied" or "role cannot be found" after create-role, attach the policy below.

### Attach IAM policy so the deploy script can run

If deploy fails with `NoSuchEntity` for the role or `AccessDeniedException` for `events:PutRule`, add the required permissions:

1. In **AWS Console** → **IAM** → **Users** → select your user (e.g. **maheshai**).
2. **Add permissions** → **Create inline policy** → **JSON** tab.
3. Paste the contents of **`iam-policy-deploy.json`** (in this folder).
4. **Next** → name the policy e.g. `BackendAlertDeploy` → **Create policy**.

Or via CLI (run with a user that has `iam:PutUserPolicy`):

```bash
aws iam put-user-policy --user-name maheshai --policy-name BackendAlertDeploy --policy-document file://deploy/backend-alert/iam-policy-deploy.json
```

Then run the deploy script again.

## Deploy

### Bash (Linux / Mac / Git Bash)

If you get "Permission denied", run `chmod +x deploy.sh` first, or use `bash deploy.sh`:

```bash
cd deploy/backend-alert
chmod +x deploy.sh
./deploy.sh <PHONE_NUMBER> [HEALTH_URL] [AWS_REGION]
# Or without chmod:
bash deploy.sh <PHONE_NUMBER> [HEALTH_URL] [AWS_REGION]
```

Examples:

```bash
./deploy.sh 7324216751
./deploy.sh 7324216751 https://maheshai.com/api/health us-east-1
```

### PowerShell (Windows)

```powershell
cd deploy\backend-alert
.\deploy.ps1 -Phone 7324216751
.\deploy.ps1 -Phone 7324216751 -HealthUrl "https://maheshai.com/api/health" -Region us-east-1
```

- **Phone:** 10-digit US number (e.g. `7324216751`). Script adds `+1` if needed.
- **Health URL:** Default `https://maheshai.com/api/health`. Override if your API is elsewhere.
- **Region:** Default `us-east-1`. Use the region where you want the Lambda and SNS.

## What the script creates

| Resource        | Name / value |
|----------------|--------------|
| SNS topic      | `backend-down-alerts` |
| Subscription   | SMS to the phone number you pass |
| Lambda         | `backend-health-check` (Python 3.12) |
| EventBridge    | Rule `backend-health-every-5min` → `rate(5 minutes)` |
| IAM role       | `backend-health-check-lambda-role` (logs + SNS Publish) |

Re-running the script updates the Lambda code and config (health URL, topic ARN); it does not create duplicate topics or rules.

## Costs

- **Lambda:** Free tier covers 1M requests/month; 5-min schedule ≈ 8.6k invocations/month.
- **EventBridge:** Free tier covers 14M events/month.
- **SNS SMS:** Per-message charge (see [AWS SNS pricing](https://aws.amazon.com/sns/pricing/)); you only pay when an alert is sent.

## Test

1. After deploy, confirm in AWS Console: **Lambda** → `backend-health-check` → Test (optional; success = no SMS).
2. To trigger an alert on purpose: temporarily set the Lambda env var `HEALTH_URL` to `https://invalid.example.com/health`, wait for the next run (or invoke the Lambda manually), then set it back.

## "No origination entities available" when verifying SMS

If you see **"No origination entities available to send"** when verifying your phone in SNS (or when the alert tries to send SMS), it means your AWS account has no **origination identity** (sender number) for US SMS. AWS requires one to send any SMS to US numbers, including sandbox verification.

### Option A – Use email instead (no setup)

You can get alerts by **email** with no origination identity:

1. Deploy as usual (the script still creates the topic and Lambda; the SMS subscription will stay "Pending confirmation" until you have origination).
2. In **AWS Console** → **SNS** → **Topics** → `backend-down-alerts` → **Create subscription**.
3. **Protocol:** Email. **Endpoint:** your email address → **Create subscription**.
4. Check your inbox, open the SNS confirmation email, and click **Confirm subscription**.

After that, when the backend is down, you’ll receive an email alert. You can use a phone’s email (e.g. `number@vtext.com`) if you want something close to SMS.

### Option B – Enable SMS with an origination number (US)

To actually send SMS (and complete phone verification), you must add a US origination identity in the same region as your SNS/Lambda (e.g. `us-east-1`):

- **Toll-free number (TFN)** – Easiest for low volume. Request a number, then register it for SMS. [Toll-free registration (AWS)](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-tfn.html).
- **10DLC** – For higher volume/branding. Register your brand and campaign, then get a number. [10DLC registration (AWS)](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-10dlc.html).

Origination identities are managed under **SMS and voice** / **Pinpoint** in the AWS Console (or the [End User Messaging](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations.html) docs). After your number is registered and approved, SNS can use it and verification/alert SMS will work.

## Remove

To delete everything (topic, Lambda, rule, role):

```bash
# Bash
aws events remove-targets --rule backend-health-every-5min --ids 1 --region us-east-1
aws events delete-rule --name backend-health-every-5min --region us-east-1
aws lambda delete-function --function-name backend-health-check --region us-east-1
aws sns list-subscriptions-by-topic --topic-arn <TOPIC_ARN>  # get subscription ARNs, then:
aws sns unsubscribe --subscription-arn <SUB_ARN>
aws sns delete-topic --topic-arn <TOPIC_ARN>
aws iam delete-role-policy --role-name backend-health-check-lambda-role --policy-name SNSPublish
aws iam detach-role-policy --role-name backend-health-check-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name backend-health-check-lambda-role
```

Replace `<TOPIC_ARN>` and `<SUB_ARN>` with the values from the console or CLI.
