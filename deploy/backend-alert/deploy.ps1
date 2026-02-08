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
# Use temp files for JSON so PowerShell does not mangle quotes when calling aws
$TrustPolicyFile = Join-Path $ScriptDir "trust-policy.json"
$SnsPolicyFile = Join-Path $ScriptDir "sns-policy.json"
# AWS CLI on Windows expects file:// with forward slashes; use ASCII so encoding is compatible
$trustJson = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
[System.IO.File]::WriteAllText($TrustPolicyFile, $trustJson, [System.Text.Encoding]::ASCII)
$snsJson = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sns:Publish","Resource":"' + $TopicArn + '"}]}'
[System.IO.File]::WriteAllText($SnsPolicyFile, $snsJson, [System.Text.Encoding]::ASCII)
$TrustFileUri = "file:///" + ($TrustPolicyFile -replace "\\", "/")
$SnsPolicyFileUri = "file:///" + ($SnsPolicyFile -replace "\\", "/")
# Run IAM commands without letting PowerShell throw on non-zero exit (e.g. role already exists)
$ErrorActionPreference = 'Continue'
$null = aws iam create-role --role-name $RoleName --assume-role-policy-document $TrustFileUri --description "Lambda role for backend health check" 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "Note: create-role returned $LASTEXITCODE (role may already exist). Continuing..." }
$null = aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>&1
$null = aws iam put-role-policy --role-name $RoleName --policy-name "SNSPublish" --policy-document $SnsPolicyFileUri 2>&1
Remove-Item $TrustPolicyFile, $SnsPolicyFile -ErrorAction SilentlyContinue
Write-Host "Waiting for IAM role to propagate (up to 25s)..."
$RoleArn = $null
$ErrorActionPreference = 'Continue'
for ($i = 1; $i -le 5; $i++) {
    Start-Sleep -Seconds 5
    $RoleArn = aws iam get-role --role-name $RoleName --query 'Role.Arn' --output text 2>&1
    if ($RoleArn -and $RoleArn.ToString().StartsWith("arn:aws:iam::")) { break }
    $RoleArn = $null
}
$ErrorActionPreference = 'Stop'
# Handle case where get-role returned an error message string
if ($RoleArn) { $RoleArn = $RoleArn.ToString().Trim() }
if (-not $RoleArn -or -not $RoleArn.StartsWith("arn:aws:iam::")) {
    Write-Host "ERROR: Could not get IAM role (create-role may have failed with 254). Check: aws iam create-role ... and ensure your account can create roles. Attach iam-policy-deploy.json if using an IAM user." -ForegroundColor Red
    exit 1
}

# --- Lambda package ---
$ZipPath = Join-Path $ScriptDir "lambda_deploy.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath }
Compress-Archive -Path (Join-Path $ScriptDir "lambda_function.py") -DestinationPath $ZipPath -Force

# --- Lambda create or update ---
$EnvVars = "Variables={HEALTH_URL=$HealthUrl,SNS_TOPIC_ARN=$TopicArn}"
$lambdaExists = $false
try {
    aws lambda get-function --function-name $FunctionName --region $Region 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { $lambdaExists = $true }
} catch {}
if ($lambdaExists) {
    Write-Host "Updating Lambda $FunctionName..."
    aws lambda update-function-code --function-name $FunctionName --zip-file "fileb://$ZipPath" --region $Region --output text --query 'LastModified'
    aws lambda update-function-configuration --function-name $FunctionName --environment $EnvVars --timeout 15 --region $Region --output text --query 'FunctionArn'
} else {
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
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Lambda create failed. Check that --role is valid and your user has lambda:CreateFunction." -ForegroundColor Red
        Remove-Item $ZipPath -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host "Waiting for Lambda to be active..."
    Start-Sleep -Seconds 5
}
$FunctionArn = (aws lambda get-function --function-name $FunctionName --region $Region --query 'Configuration.FunctionArn' --output text 2>&1)
Remove-Item $ZipPath -ErrorAction SilentlyContinue
if (-not $FunctionArn -or -not $FunctionArn.StartsWith("arn:aws:lambda:")) {
    Write-Host "ERROR: Could not get Lambda ARN. Deploy stopped before EventBridge." -ForegroundColor Red
    exit 1
}

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
$putRuleOut = aws events put-rule `
    --name $RuleName `
    --schedule-expression "rate(5 minutes)" `
    --state ENABLED `
    --description "Invoke backend health check Lambda every 5 min" `
    --region $Region `
    --output text --query 'RuleArn' 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: EventBridge PutRule failed. Your user needs events:PutRule. Attach iam-policy-deploy.json to your IAM user (e.g. maheshai)." -ForegroundColor Red
    Write-Host "SNS topic and Lambda were created. You can add the EventBridge rule manually in the AWS Console (Events > Rules > Create rule, schedule rate(5 minutes), target = $FunctionName)." -ForegroundColor Yellow
    exit 1
}
aws events put-targets --rule $RuleName --targets "Id=1,Arn=$FunctionArn" --region $Region
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: EventBridge PutTargets failed." -ForegroundColor Red
    exit 1
}

Write-Host "Done. Lambda runs every 5 minutes. You will receive an SMS if $HealthUrl fails."
