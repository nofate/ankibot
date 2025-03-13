#!/bin/bash

# Configuration
STACK_NAME="ankibot"
TEMPLATE_FILE="template.yaml"
REGION="us-east-1"
DEPLOYMENT_BUCKET="ankibot-deployment"

# Start LocalStack if not running
if ! curl -s http://localhost:4566/_localstack/health | grep -q "\"s3\": \"running\""; then
  echo "Starting LocalStack..."
  LOCALSTACK_CONFIG=localstack-config.json localstack start -d
  sleep 5
fi

# Create S3 buckets
echo "Creating S3 buckets..."
awslocal s3 mb s3://ankibot-deployment
awslocal s3 mb s3://ankibot-audio-000000000000
awslocal s3 mb s3://ankibot-decks-000000000000

# Create temp directories
mkdir -p build/layer/python
mkdir -p build/functions

# Install dependencies for layer
pip install -r requirements.txt -t build/layer/python

# Create layer package
cd build/layer
zip -r ../../layer.zip .
cd ../..

# Package function code
zip -r build/functions.zip *.py

# Upload packages to S3
awslocal s3 cp layer.zip s3://ankibot-deployment/
awslocal s3 cp build/functions.zip s3://ankibot-deployment/

# Deploy CloudFormation stack
awslocal cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --parameter-overrides \
    TelegramToken="test-token" \
    AnthropicApiKey="test-key" \
    DeploymentBucket="ankibot-deployment" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

# Clean up
rm -rf build
rm layer.zip

echo "Deployment to LocalStack complete!"