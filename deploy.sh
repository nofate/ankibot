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
mkdir -p templates

# Install dependencies for layer
pip install -r requirements.txt -t build/layer/python

# Create layer package
cd build/layer
zip -r ../../layer.zip .
cd ../..

# Package function code
zip -r functions.zip *.py messages.yml templates/

# Calculate code hash
LAYER_HASH=$(md5sum layer.zip | awk '{print $1}')
FUNCTIONS_HASH=$(md5sum functions.zip | awk '{print $1}')
CODE_HASH="${LAYER_HASH:0:8}-${FUNCTIONS_HASH:0:8}"
echo "Code hash: $CODE_HASH"

# Rename zip files with hash to avoid S3 caching
LAYER_ZIP="layer-${LAYER_HASH:0:8}.zip"
FUNCTIONS_ZIP="functions-${FUNCTIONS_HASH:0:8}.zip"
mv layer.zip $LAYER_ZIP
mv functions.zip $FUNCTIONS_ZIP

# Upload the hashed versions
aws s3 cp $LAYER_ZIP s3://$DEPLOYMENT_BUCKET/$LAYER_ZIP
aws s3 cp $FUNCTIONS_ZIP s3://$DEPLOYMENT_BUCKET/$FUNCTIONS_ZIP

# Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --parameter-overrides \
    TelegramToken=$TELEGRAM_TOKEN \
    AnthropicApiKey=$ANTHROPIC_API_KEY \
    CodeVersionHash=$CODE_HASH \
    LayerZipName=$LAYER_ZIP \
    FunctionsZipName=$FUNCTIONS_ZIP \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-disable-rollback \
  --region $REGION

# Clean up
rm -rf build
rm $LAYER_ZIP
rm $FUNCTIONS_ZIP

echo "Deployment completed with code hash: $CODE_HASH" 