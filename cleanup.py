import boto3
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Check if variable is loaded
bucket_name = os.environ.get('AUDIO_BUCKET')
if not bucket_name:
    raise ValueError("AUDIO_BUCKET environment variable is not set")

def cleanup_s3():
    """Delete all files from S3 bucket"""
    try:
        s3 = boto3.client('s3')
        
        # List all objects in the bucket
        paginator = s3.get_paginator('list_objects_v2')
        
        deleted_count = 0
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                # Get list of objects to delete
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                
                # Delete objects in batches
                s3.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects}
                )
                
                deleted_count += len(objects)
        
        print(f"✓ Deleted {deleted_count} files from S3 bucket: {bucket_name}")
        
    except Exception as e:
        print(f"Error cleaning up S3: {str(e)}")

def cleanup_dynamodb():
    """Delete all items from DynamoDB table"""
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('language_entries')
        
        # Scan for all items
        response = table.scan()
        items = response.get('Items', [])
        
        # Delete each item
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={
                        'id': item['id']
                    }
                )
        
        print(f"✓ Deleted {len(items)} entries from DynamoDB table: language_entries")
        
    except Exception as e:
        print(f"Error cleaning up DynamoDB: {str(e)}")

def main():
    print("Starting cleanup...")
    cleanup_s3()
    cleanup_dynamodb()
    print("Cleanup complete!")

if __name__ == "__main__":
    main() 