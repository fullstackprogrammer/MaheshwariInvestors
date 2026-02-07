#!/usr/bin/env bash
# Deploy backend health-check alert: SNS topic + SMS subscription + Lambda + EventBridge (every 5 min).
# Requires: AWS CLI configured (aws configure), jq optional but helpful.
#
# Usage:
#   ./deploy.sh <PHONE_NUMBER> [HEALTH_URL] [AWS_REGION]
# Example:
#   ./deploy.sh 7324216751
#   ./deploy.sh 7324216751 https://maheshai.com/api/health us-east-1

set -e
PHONE="${1:?Usage: $0 <PHONE_NUMBER> [HEALTH_URL] [AWS_REGION]}"
HEALTH_URL="${2:-https://maheshai.com/api/health}"
AWS_REGION="${3:-us-east-1}"

TOPIC_NAME="backend-down-alerts"
FUNCTION_NAME="backend-health-check"
RULE_NAME="backend-health-every-5min"
ROLE_NAME="backend-health-check-lambda-role"
ZIP_FILE="$(dirname "$0")/lambda_deploy.zip"

echo "Phone: $PHONE"
echo "Health URL: $HEALTH_URL"
echo "Region: $AWS_REGION"

# --- SNS topic ---
echo "Creating SNS topic $TOPIC_NAME..."
TOPIC_ARN=$(aws sns create-topic --name "$TOPIC_NAME" --region "$AWS_REGION" --query 'TopicArn' --output text 2>/dev/null || true)
if [ -z "$TOPIC_ARN" ]; then
  TOPIC_ARN=$(aws sns list-topics --region "$AWS_REGION" --query "Topics[?contains(TopicArn, \`$TOPIC_NAME\`)].TopicArn" --output text)
fi
echo "Topic ARN: $TOPIC_ARN"

# --- SMS subscription ---
echo "Subscribing $PHONE (SMS) to topic..."
# Use +1 if 10 digits
ENDPOINT="$PHONE"
if [[ "$PHONE" =~ ^[0-9]{10}$ ]]; then
  ENDPOINT="+1$PHONE"
fi
aws sns subscribe --topic-arn "$TOPIC_ARN" --protocol sms --notification-endpoint "$ENDPOINT" --region "$AWS_REGION" 2>/dev/null || echo "(Subscription may already exist)"

# --- IAM role for Lambda ---
echo "Creating IAM role $ROLE_NAME..."
TRUST='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$TRUST" --description "Lambda role for backend health check" 2>/dev/null || true
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>/dev/null || true
SNS_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sns:Publish","Resource":"'"$TOPIC_ARN"'"}]}'
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "SNSPublish" --policy-document "$SNS_POLICY" 2>/dev/null || true
echo "Waiting for IAM role to propagate..."
sleep 10
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

# --- Lambda package ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
zip -q -j "$ZIP_FILE" lambda_function.py

# --- Lambda create or update ---
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" &>/dev/null; then
  echo "Updating Lambda $FUNCTION_NAME..."
  aws lambda update-function-code --function-name "$FUNCTION_NAME" --zip-file "fileb://$ZIP_FILE" --region "$AWS_REGION" --output text --query 'LastModified'
  aws lambda update-function-configuration --function-name "$FUNCTION_NAME" --environment "Variables={HEALTH_URL=$HEALTH_URL,SNS_TOPIC_ARN=$TOPIC_ARN}" --timeout 15 --region "$AWS_REGION" --output text --query 'FunctionArn'
else
  echo "Creating Lambda $FUNCTION_NAME..."
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler lambda_function.lambda_handler \
    --zip-file "fileb://$ZIP_FILE" \
    --timeout 15 \
    --environment "Variables={HEALTH_URL=$HEALTH_URL,SNS_TOPIC_ARN=$TOPIC_ARN}" \
    --region "$AWS_REGION" \
    --output text --query 'FunctionArn'
  echo "Waiting for Lambda to be active..."
  sleep 5
fi
FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$AWS_REGION" --query 'Configuration.FunctionArn' --output text)
rm -f "$ZIP_FILE"

# --- Allow EventBridge to invoke Lambda ---
echo "Adding EventBridge invoke permission..."
aws lambda add-permission \
  --function-name "$FUNCTION_NAME" \
  --statement-id "EventBridgeInvoke" \
  --action "lambda:InvokeFunction" \
  --principal "events.amazonaws.com" \
  --source-arn "arn:aws:events:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):rule/$RULE_NAME" \
  --region "$AWS_REGION" 2>/dev/null || echo "(Permission may already exist)"

# --- EventBridge rule (every 5 minutes) ---
echo "Creating EventBridge rule $RULE_NAME..."
aws events put-rule \
  --name "$RULE_NAME" \
  --schedule-expression "rate(5 minutes)" \
  --state ENABLED \
  --description "Invoke backend health check Lambda every 5 min" \
  --region "$AWS_REGION" \
  --output text --query 'RuleArn'

aws events put-targets \
  --rule "$RULE_NAME" \
  --targets "Id=1,Arn=$FUNCTION_ARN" \
  --region "$AWS_REGION"

echo "Done. Lambda runs every 5 minutes. You will receive an SMS if $HEALTH_URL fails."
