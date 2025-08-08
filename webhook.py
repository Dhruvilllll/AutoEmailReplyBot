import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes
)
from email_bot import gmail_authenticate, generate_gpt_reply, send_email, CURRENT_EMAIL

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


@telegram_app.on_update()
async def handle_update(update: Update):
    await telegram_app.process_update(update)


@app.post("/")
async def root(request: Request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await handle_update(update)
    return {"status": "ok"}


@telegram_app.command_handler("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your Auto Email Reply Bot, Dhruvil!")


@telegram_app.callback_query_handler(pattern="professional|casual|friendly|ignore")
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tone = query.data.lower()

    sender = CURRENT_EMAIL.get('sender', 'Unknown')
    subject = CURRENT_EMAIL.get('subject', '(No Subject)')
    snippet = CURRENT_EMAIL.get('snippet', '')

    draft = await generate_gpt_reply(tone, sender, subject, snippet)

    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=(
            f"📝 *{tone.title()}* Draft:\n"
            f"*Subject:* {subject}\n\n"
            f"📄 *Draft:*\n```\n{draft}\n```\n"
            f"Do you want to send it?"
        ),
        parse_mode="Markdown"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Yes, Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_send")]
    ]
    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text="Please confirm:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data['draft'] = draft


@telegram_app.callback_query_handler(pattern="confirm_send|cancel_send")
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "confirm_send":
        service = gmail_authenticate()
        draft = context.user_data.get('draft')
        send_email(
            service,
            CURRENT_EMAIL['sender'],
            CURRENT_EMAIL['subject'],
            draft,
            thread_id=CURRENT_EMAIL.get('threadId')
        )
        await query.edit_message_text("✅ Email sent successfully.")
    else:
        await query.edit_message_text("❌ Email sending cancelled.")
