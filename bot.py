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

# Get telegram token from environment variable
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Create application instance once, outside the handler
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available commands:
/help - Show this help message
/export - Export your data
/list - Show available items
    """
    await update.message.reply_text(help_text)

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Placeholder for export functionality
    await update.message.reply_text("Export functionality will be available soon!")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Show web app button
    await update.message.reply_text(
        "Click below to open the list:",
        reply_markup={
            "inline_keyboard": [[{
                "text": "Open List",
                "web_app": {"url": f"https://example.com"}
            }]]
        }
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle regular messages
    await update.message.reply_text(f"You said: {update.message.text}")

# Initialize handlers once
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("export", export_command))
application.add_handler(CommandHandler("list", list_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Initialize the application
import asyncio
loop = asyncio.get_event_loop()
loop.run_until_complete(application.initialize())

def lambda_handler(event, context):
    """AWS Lambda handler"""
    
    try:
        # Parse the update - Function URLs have a different event structure
        if 'body' in event and isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event
            
        # Debug logging
        print("Received body:", body)
            
        # Ensure we're passing the actual Telegram update object
        if isinstance(body, dict) and 'message' in body:
            update = Update.de_json(body, application.bot)
        else:
            return {
                'statusCode': 400,
                'body': 'Invalid update format'
            }
        
        # Process update
        async def process_update():
            await application.process_update(update)
            
        loop.run_until_complete(process_update())
        
        return {
            'statusCode': 200,
            'body': 'OK'
        }
    except Exception as e:
        print("Error:", str(e))  # Debug logging
        return {
            'statusCode': 500,
            'body': str(e)
        } 