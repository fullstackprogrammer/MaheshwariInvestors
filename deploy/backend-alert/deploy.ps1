# Deploy backend health-check alert: SNS topic + SMS subscription + Lambda + EventBridge (every 5 min).
# Requires: AWS CLI installed and configured (aws configure).
#
# Usage:
#   .\deploy.ps1 -Phone 7324216751
#   .\deploy.ps1 -Phone 7324216751 -HealthUrl "https://maheshai.com/api/health" -Region us-east-1

param(
    [Parameter(Mandatory = $true)]
    [string] $Phone,
    [string] $HealthUrl = "https://maheshai.com/api/health",
    [string] $Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$TopicName = "backend-down-alerts"
$FunctionName = "backend-health-check"
$RuleName = "backend-health-every-5min"
$RoleName = "backend-health-check-lambda-role"
$ScriptDir = $PSScriptRoot

Write-Host "Phone: $Phone"
Write-Host "Health URL: $HealthUrl"
Write-Host "Region: $Region"

# --- SNS topic ---
Write-Host "Creating SNS topic $TopicName..."
try {
    $topic = aws sns create-topic --name $TopicName --region $Region 2>&1 | ConvertFrom-Json
    $TopicArn = $topic.TopicArn
} catch {
    $TopicArn = (aws sns list-topics --region $Region --query "Topics[?contains(TopicArn, '$TopicName')].TopicArn" --output text)
}
Write-Host "Topic ARN: $TopicArn"

# --- SMS subscription ---
Write-Host "Subscribing $Phone (SMS) to topic..."
$Endpoint = if ($Phone -match '^\d{10}$') { "+1$Phone" } else { $Phone }
try {
    aws sns subscribe --topic-arn $TopicArn --protocol sms --notification-endpoint $Endpoint --region $Region 2>&1
} catch {
    Write-Host "(Subscription may already exist)"
}

# --- IAM role for Lambda ---
Write-Host "Creating IAM role $RoleName..."
$Trust = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
try { aws iam create-role --role-name $RoleName --assume-role-policy-document $Trust --description "Lambda role for backend health check" 2>&1 } catch {}
try { aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>&1 } catch {}
$SnsPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sns:Publish","Resource":"' + $TopicArn + '"}]}'
try { aws iam put-role-policy --role-name $RoleName --policy-name "SNSPublish" --policy-document $SnsPolicy 2>&1 } catch {}
Write-Host "Waiting for IAM role to propagate..."
Start-Sleep -Seconds 10
$RoleArn = (aws iam get-role --role-name $RoleName --query 'Role.Arn' --output text)

# --- Lambda package ---
$ZipPath = Join-Path $ScriptDir "lambda_deploy.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath }
Compress-Archive -Path (Join-Path $ScriptDir "lambda_function.py") -DestinationPath $ZipPath -Force

# --- Lambda create or update ---
$EnvVars = "Variables={HEALTH_URL=$HealthUrl,SNS_TOPIC_ARN=$TopicArn}"
try {
    aws lambda get-function --function-name $FunctionName --region $Region 2>&1 | Out-Null
    Write-Host "Updating Lambda $FunctionName..."
    aws lambda update-function-code --function-name $FunctionName --zip-file "fileb://$ZipPath" --region $Region --output text --query 'LastModified'
    aws lambda update-function-configuration --function-name $FunctionName --environment $EnvVars --timeout 15 --region $Region --output text --query 'FunctionArn'
} catch {
    Write-Host "Creating Lambda $FunctionName..."
    aws lambda create-function `
        --function-name $FunctionName `
        --runtime python3.12 `
        --role $RoleArn `
        --handler lambda_function.lambda_handler `
        --zip-file "fileb://$ZipPath" `
        --timeout 15 `
        --environment $EnvVars `
        --region $Region `
        --output text --query 'FunctionArn'
    Write-Host "Waiting for Lambda to be active..."
    Start-Sleep -Seconds 5
}
$FunctionArn = (aws lambda get-function --function-name $FunctionName --region $Region --query 'Configuration.FunctionArn' --output text)
Remove-Item $ZipPath -ErrorAction SilentlyContinue

# --- Allow EventBridge to invoke Lambda ---
$AccountId = (aws sts get-caller-identity --query Account --output text)
$SourceArn = "arn:aws:events:${Region}:${AccountId}:rule/$RuleName"
Write-Host "Adding EventBridge invoke permission..."
try {
    aws lambda add-permission `
        --function-name $FunctionName `
        --statement-id "EventBridgeInvoke" `
        --action "lambda:InvokeFunction" `
        --principal "events.amazonaws.com" `
        --source-arn $SourceArn `
        --region $Region 2>&1
} catch {
    Write-Host "(Permission may already exist)"
}

# --- EventBridge rule (every 5 minutes) ---
Write-Host "Creating EventBridge rule $RuleName..."
aws events put-rule `
    --name $RuleName `
    --schedule-expression "rate(5 minutes)" `
    --state ENABLED `
    --description "Invoke backend health check Lambda every 5 min" `
    --region $Region `
    --output text --query 'RuleArn'

aws events put-targets --rule $RuleName --targets "Id=1,Arn=$FunctionArn" --region $Region

Write-Host "Done. Lambda runs every 5 minutes. You will receive an SMS if $HealthUrl fails."
