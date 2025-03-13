#!/bin/bash

# Configuration
STACK_NAME="ankibot"
TEMPLATE_FILE="template.yaml"
DEPLOYMENT_BUCKET="ankibot-deployment"
REGION="eu-central-1"

# Create deployment bucket if it doesn't exist
aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION

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
aws s3 cp layer.zip s3://$DEPLOYMENT_BUCKET/
aws s3 cp build/functions.zip s3://$DEPLOYMENT_BUCKET/

# Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --parameter-overrides \
    TelegramToken=$TELEGRAM_TOKEN \
    AnthropicApiKey=$ANTHROPIC_API_KEY \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

# Clean up
rm -rf build
rm layer.zip 