from telegram import Update, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import json
import os
import boto3
import asyncio
from core import LanguageEntry

# Get telegram token from environment variable
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
QUEUE_URL = os.environ.get('QUEUE_URL')

# Initialize AWS SQS client
sqs = boto3.client('sqs')

# Initialize bot and event loop
bot = Application.builder().token(TELEGRAM_TOKEN).build().bot
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def help_command(update: Update):
    help_text = """
        Available commands:
        /help - Show this help message
        /export - Export your data
        /list - Show available items
    """
    loop.run_until_complete(update.message.reply_text(help_text))

def export_command(update: Update):
    loop.run_until_complete(update.message.reply_text("Export functionality will be available soon!"))

def list_command(update: Update):
    """Show all saved German words/phrases"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan()
        items = entries.get('Items', [])
        
        if not items:
            loop.run_until_complete(update.message.reply_text(
                "No entries found in the database yet."
            ))
            return
        
        # Format the list with query, translation and definition
        message_lines = []
        for item in items:
            message_lines.append(
                f"• {item['query']}\n"
                f"  {item['definition']} | {item['translation']}"
            )
        
        # Join all lines and send
        message = "Saved entries:\n\n" + "\n\n".join(message_lines)
        
        # Split message if too long (Telegram has 4096 char limit)
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                loop.run_until_complete(update.message.reply_text(chunk))
        else:
            loop.run_until_complete(update.message.reply_text(message))
            
    except Exception as e:
        print(f"Error in list_command: {str(e)}")
        loop.run_until_complete(update.message.reply_text(
            "Sorry, there was an error retrieving the entries."
        ))

def handle_message(update: Update):
    try:
        # Prepare message for queue
        message = {
            'user_id': update.effective_user.id,
            'username': update.effective_user.username,
            'text': update.message.text,
            'timestamp': update.message.date.isoformat()
        }
        
        # Send to SQS
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        
        # Reply to user
        loop.run_until_complete(update.message.reply_text(
            f"Your message has been queued! You said: {update.message.text}"
        ))
    except Exception as e:
        print(f"Error sending to SQS: {str(e)}")
        loop.run_until_complete(update.message.reply_text(
            "Sorry, there was an error processing your message."
        ))

def lambda_handler(event, context):
    """AWS Lambda handler"""
    
    try:
        # Parse the update - Handle both Function URL and API Gateway events
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
                print("Parsed body from string:", body)
            else:
                body = event['body']  # API Gateway might already parse JSON
                print("Using pre-parsed body:", body)
        else:
            body = event
            print("Using event as body:", body)
            
        # Debug logging
        print("Processing body:", body)
            
        # Ensure we're passing the actual Telegram update object
        if isinstance(body, dict) and 'message' in body:
            print("Found message in body")
            update = Update.de_json(body, bot)
            
            # Route to appropriate handler
            text = update.message.text
            print(f"Processing message text: {text}")
            
            if text.startswith('/help'):
                help_command(update)
            elif text.startswith('/export'):
                export_command(update)
            elif text.startswith('/list'):
                list_command(update)
            else:
                handle_message(update)
                
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'status': 'OK'})
            }
        else:
            print("Invalid body format:", body)
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'Invalid update format'})
            }
            
    except Exception as e:
        print("Error:", str(e))
        print("Event that caused error:", event)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': str(e)})
        } 