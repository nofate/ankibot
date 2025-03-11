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
import genanki
import io
import random
import time
from anki import create_anki_deck

# Get environment variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
QUEUE_URL = os.environ.get('QUEUE_URL')
DECKS_BUCKET = os.environ.get('DECKS_BUCKET')

# Initialize AWS clients
sqs = boto3.client('sqs')
s3 = boto3.client('s3')

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

async def export_command(update: Update):
    """Generate and share Anki deck"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan().get('Items', [])
        
        if not entries:
            await update.message.reply_text(
                "No entries found to export."
            )
            return
            
        # Create Anki deck
        package_buf = create_anki_deck(entries)
        
        # Generate filename with user ID for tracking
        timestamp = int(time.time())
        filename = f"deck_{update.effective_user.id}_{timestamp}.apkg"
        
        # Upload backup to S3
        try:
            s3.upload_fileobj(
                io.BytesIO(package_buf.getvalue()),  # Create new buffer for S3
                DECKS_BUCKET,
                filename,
                ExtraArgs={'ContentType': 'application/octet-stream'}
            )
            print(f"Backup saved to S3: {filename}")
        except Exception as e:
            print(f"Warning: Failed to save backup to S3: {str(e)}")
            # Continue anyway to send file to user
        
        # Send file directly to user
        await update.message.reply_document(
            document=package_buf.getvalue(),
            filename=f"german_vocab_{timestamp}.apkg",  # Clean filename for user
            caption="Here's your Anki deck!"
        )
            
    except Exception as e:
        print(f"Error generating deck: {str(e)}")
        await update.message.reply_text(
            "Sorry, there was an error generating your deck."
        )

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
        # Parse the update
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event
            
        # Debug logging
        print("Processing body:", body)
            
        # Ensure we're passing the actual Telegram update object
        if isinstance(body, dict) and 'message' in body:
            update = Update.de_json(body, bot)
            
            # Route to appropriate handler
            text = update.message.text
            print(f"Processing message text: {text}")
            
            # Handle known commands only
            if text.startswith('/'):
                if text.startswith('/help'):
                    help_command(update)
                elif text.startswith('/export'):
                    loop.run_until_complete(export_command(update))
                elif text.startswith('/list'):
                    list_command(update)
                else:
                    # Unknown command - inform user
                    loop.run_until_complete(update.message.reply_text(
                        "Unknown command. Type /help to see available commands."
                    ))
                    return {
                        'statusCode': 200,
                        'body': json.dumps({'status': 'Unknown command'})
                    }
            else:
                # Not a command - process as regular message
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