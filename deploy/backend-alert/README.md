# Backend health-check alert (SNS + Lambda + EventBridge)

Sends an SMS to your phone when the backend API stops responding. Runs a Lambda every 5 minutes; if the health check fails, Lambda publishes to SNS and you get a text.

## Prerequisites

- **AWS CLI** installed and configured (`aws configure` with credentials and region).
- **Bash** (for `deploy.sh`) or **PowerShell** (for `deploy.ps1`). On Windows you can use Git Bash for `deploy.sh`.

## Deploy

### Bash (Linux / Mac / Git Bash)

```bash
cd deploy/backend-alert
./deploy.sh <PHONE_NUMBER> [HEALTH_URL] [AWS_REGION]
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
