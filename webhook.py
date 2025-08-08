import os
import sys
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes
import asyncio

from email_bot import (
    start_command, handle_choice, handle_confirmation
)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Initialize bot app
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(CallbackQueryHandler(handle_choice, pattern="professional|casual|friendly|ignore"))
app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="confirm_send|cancel_send"))

# Vercel handler
def handler(request):
    try:
        data = json.loads(request.body)
        update = Update.de_json(data, app.bot)
        asyncio.run(app.process_update(update))
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Update processed"})
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
