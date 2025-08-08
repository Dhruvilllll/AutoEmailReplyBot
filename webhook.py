# webhook.py
import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from email_bot import gmail_authenticate, generate_gpt_reply, send_email

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

app = FastAPI()

telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

CURRENT_EMAIL = {}
DRAFT_REPLY = ""

# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your email assistant bot.\nI'll notify you of new emails and help you reply directly from Telegram."
    )

# Tone Selection
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DRAFT_REPLY
    query = update.callback_query
    await query.answer()
    tone = query.data.lower()

    sender = CURRENT_EMAIL.get('sender', 'Unknown')
    subject = CURRENT_EMAIL.get('subject', '(No Subject)')
    snippet = CURRENT_EMAIL.get('snippet', '')

    DRAFT_REPLY = await generate_gpt_reply(tone, sender, subject, snippet)

    keyboard = [
        [InlineKeyboardButton("✅ Yes, Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
    ]
    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=(
            f"🤖 *Drafted {tone.title()} Reply:*\n\n"
            f"{DRAFT_REPLY}\n\n"
            "Shall I send it?"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# Confirmation
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_send":
        service = gmail_authenticate()
        send_email(
            service,
            CURRENT_EMAIL['sender'],
            CURRENT_EMAIL['subject'],
            DRAFT_REPLY,
            thread_id=CURRENT_EMAIL.get('threadId')
        )
        await query.edit_message_text("✅ Email sent successfully.")
    else:
        await query.edit_message_text("❌ Cancelled.")

# Handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(handle_choice, pattern="professional|casual|friendly"))
telegram_app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="confirm_send|cancel_send"))

# FastAPI Endpoint
@app.post("/")
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
