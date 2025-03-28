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
from core import LanguageEntry, User, LanguageLevel
import genanki
import io
import random
import time
from anki import create_anki_deck
from localization import t, set_language

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

def extract_command_args(text: str) -> list:
    """Extract command arguments from message text"""
    # Split by spaces and remove the command itself (first element)
    parts = text.split()
    if len(parts) > 1:
        return parts[1:]
    return []

def get_user_language(update: Update):
    """Get the user's language from Telegram"""
    language_code = update.effective_user.language_code
    if language_code:
        # Simplify language code (e.g., 'en-US' -> 'en')
        language_code = language_code.split('-')[0].lower()
        
    # Return the language code if it's supported, otherwise return the default
    if language_code in ["ru", "en"]:
        return language_code
    return "ru"  # Default to Russian

def help_command(update: Update):
    loop.run_until_complete(update.message.reply_text(t("help_text")))

async def export_command(update: Update):
    """Generate and share Anki deck"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan().get('Items', [])
        
        if not entries:
            await update.message.reply_text(t("empty_collection"))
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
            caption=t("deck_ready")
        )
            
    except Exception as e:
        print(f"Error generating deck: {str(e)}")
        await update.message.reply_text(t("deck_error"))

def list_command(update: Update):
    """Show all saved German words/phrases"""
    try:
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan()
        items = entries.get('Items', [])
        
        if not items:
            loop.run_until_complete(update.message.reply_text(t("empty_collection")))
            return
        
        # Format the list with query, translation and definition
        message_lines = []
        for item in items:
            message_lines.append(
                f"• {item['query']} | {item['definition']} | {item['translation']}"
            )
        
        # Join all lines and send
        message = f"{t('collection_title')}\n\n" + "\n\n".join(message_lines)
        
        # Split message if too long (Telegram has 4096 char limit)
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                loop.run_until_complete(update.message.reply_text(chunk))
        else:
            loop.run_until_complete(update.message.reply_text(message))
            
    except Exception as e:
        print(f"Error in list_command: {str(e)}")
        loop.run_until_complete(update.message.reply_text(t("collection_error")))

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
        loop.run_until_complete(update.message.reply_text(t("message_queued")))
    except Exception as e:
        print(f"Error sending to SQS: {str(e)}")
        loop.run_until_complete(update.message.reply_text(t("message_error")))

async def level_command(update: Update, args: list = None):
    """Handle /level command to set or get user's language level"""
    user_id = update.effective_user.id
    user = User.get_user(user_id)
    
    if not args:
        # No arguments, return current level
        await update.message.reply_text(
            t("level_current").format(level=user.level.value)
        )
        return
    
    # Set new level
    new_level = args[0].upper()
    try:
        # Convert string to enum
        level_enum = LanguageLevel.from_string(new_level)
        # Update user
        user.level = level_enum
        user.save()
        await update.message.reply_text(
            t("level_updated").format(level=level_enum.value)
        )
    except ValueError as e:
        await update.message.reply_text(
            t("level_invalid").format(
                levels=", ".join(LanguageLevel.get_all_values())
            )
        )

async def context_command(update: Update, args: list = None):
    """Handle /context command to set or get user's context"""
    user_id = update.effective_user.id
    user = User.get_user(user_id)
    
    if not args:
        # No arguments, return current context
        current_context = user.context if user.context else t("context_empty")
        await update.message.reply_text(
            t("context_current").format(context=current_context)
        )
        return
    
    # Set new context
    new_context = ' '.join(args)
    user.context = new_context
    user.save()
    await update.message.reply_text(
        t("context_updated")
    )


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
            
            # Set global language based on user's language
            language = get_user_language(update)
            set_language(language)
            
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
                elif text.startswith('/level'):
                    args = extract_command_args(text)
                    loop.run_until_complete(level_command(update, args))
                elif text.startswith('/context'):
                    args = extract_command_args(text)
                    loop.run_until_complete(context_command(update, args))
                else:
                    # Unknown command - inform user
                    loop.run_until_complete(update.message.reply_text(t("unknown_command")))
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