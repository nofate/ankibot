#!/bin/bash

# Configuration
STACK_NAME="ankibot"
TEMPLATE_FILE="template.yaml"
DEPLOYMENT_BUCKET="ankibot-deployment"
REGION="eu-central-1"

# Create deployment bucket if it doesn't exist
aws s3 mb s3://$DEPLOYMENT_BUCKET --region $REGION 2>/dev/null || true

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
zip -r build/functions.zip *.py messages.yml

# Calculate code hash
LAYER_HASH=$(md5sum layer.zip | awk '{print $1}')
FUNCTIONS_HASH=$(md5sum build/functions.zip | awk '{print $1}')
CODE_HASH="${LAYER_HASH:0:8}-${FUNCTIONS_HASH:0:8}"
echo "Code hash: $CODE_HASH"

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
    CodeVersionHash=$CODE_HASH \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

# Clean up
rm -rf build
rm layer.zip

echo "Deployment completed with code hash: $CODE_HASH" 