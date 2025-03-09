import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Process messages from SQS queue
    """
    try:
        # Log the entire event for debugging
        print("Received event:", json.dumps(event, indent=2))
        
        # Process each record from SQS
        for record in event['Records']:
            # Parse the message body
            message = json.loads(record['body'])
            
            # Log the message details in one line
            print(f"Message: [ID: {record['messageId']}] User {message.get('username')}({message.get('user_id')}) sent: '{message.get('text')}' at {message.get('timestamp')}")
            
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"Processed {len(event['Records'])} messages",
                'timestamp': datetime.utcnow().isoformat()
            })
        }
            
    except Exception as e:
        print(f"Error processing messages: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        } 