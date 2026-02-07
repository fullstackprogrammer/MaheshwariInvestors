"""
Lambda: check backend health and send SNS SMS when unreachable.
Invoked every 5 minutes by EventBridge. Set HEALTH_URL and SNS_TOPIC_ARN in env.
"""
import urllib.request
import os

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
