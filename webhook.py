import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from email_bot import gmail_authenticate, generate_gpt_reply, send_email
from googleapiclient.errors import HttpError

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()

CURRENT_EMAIL = {}
DRAFT_REPLY = ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your email assistant bot.\nI'll notify you of new emails and help you reply directly from Telegram.")

# --- Handle Tone Choice and Draft Generation ---
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DRAFT_REPLY
    query = update.callback_query
    await query.answer()
    tone = query.data.lower()

    sender = CURRENT_EMAIL.get('sender', 'Unknown')
    subject = CURRENT_EMAIL.get('subject', '(No Subject)')
    snippet = CURRENT_EMAIL.get('snippet', '')

    DRAFT_REPLY = await generate_gpt_reply(tone, sender, subject, snippet)

    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=(
            f"🤖 I'm drafting a *{tone.title()}* reply...\n\n"
            f"📄 *Draft:*\n```\n{DRAFT_REPLY}\n```\n"
            f"Shall I send it?"
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

# --- Handle Confirmation to Send or Cancel ---
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "confirm_send":
        service = gmail_authenticate()
        send_email(
            service,
            CURRENT_EMAIL['sender'],
            CURRENT_EMAIL['subject'],
            DRAFT_REPLY,
            thread_id=CURRENT_EMAIL.get('threadId')
        )
        await query.edit_message_text("✅ Email sent successfully.")
    elif choice == "cancel_send":
        await query.edit_message_text("❌ Email sending cancelled.")

# --- Email Monitoring ---
async def watch_emails():
    service = gmail_authenticate()

    import time
    start_time = int(time.time())  # Current Unix timestamp at start

    while True:
        try:
            q = f"is:unread after:{start_time}"
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], q=q, maxResults=1).execute()
            messages = results.get('messages', [])

            if messages:
                msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
                headers = msg.get('payload', {}).get('headers', [])
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                snippet = msg.get('snippet', '')

                # 🔍 Extract name and email ID
                if "<" in sender and ">" in sender:
                    name = sender.split("<")[0].strip().strip('"')
                    email_id = sender.split("<")[1].strip(">")
                else:
                    name = "Unknown"
                    email_id = sender

                # ✅ Print to terminal
                print(f"📥 New Email Received From: {name} <{email_id}>")
                print(f"📌 Subject: {subject}")
                print(f"📄 Snippet: {snippet}\n")

                global CURRENT_EMAIL
                CURRENT_EMAIL = {
                    'id': msg['id'],
                    'threadId': msg.get('threadId'),
                    'sender': sender,
                    'subject': subject,
                    'snippet': snippet
                }

                keyboard = [
                    [InlineKeyboardButton("Professional", callback_data="professional")],
                    [InlineKeyboardButton("Casual", callback_data="casual")],
                    [InlineKeyboardButton("Friendly", callback_data="friendly")],
                    [InlineKeyboardButton("Ignore", callback_data="cancel_send")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await app.bot.send_message(
                    chat_id=TELEGRAM_USER_ID,
                    text=(
                        f"📬 *New Email!*\n"
                        f"*From:* {sender}\n"
                        f"*Subject:* {subject}\n"
                        f"*Snippet:* {snippet}"
                    ),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )

                # Mark email as read
                service.users().messages().modify(
                    userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}
                ).execute()

        except HttpError as error:
            print(f"❌ Gmail API error: {error}")
        except Exception as e:
            print(f"⚠️ Error while watching emails: {e}")

        await asyncio.sleep(15)

from telegram.ext import Application

async def handle_webhook_update(update: Update):
    await app.process_update(update)

# --- Main ---
async def main():
    global app
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="professional|casual|friendly|ignore"))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="confirm_send|cancel_send"))

    print("🚀 Bot started. Watching for new emails...")
    asyncio.create_task(watch_emails())
    await app.run_polling()

    print("🚀 Bot started. Watching for new emails...")
    asyncio.create_task(watch_emails())

   async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_send":
        service = gmail_authenticate()
        send_email(
            service,
            CURRENT_EMAIL["sender"],
            CURRENT_EMAIL["subject"],
            DRAFT_REPLY,
            thread_id=CURRENT_EMAIL.get("threadId")
        )
        await query.edit_message_text("✅ Email sent!")
    else:
        await query.edit_message_text("❌ Cancelled.")

# -- Telegram Setup --
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(handle_tone, pattern="professional|casual|friendly"))
telegram_app.add_handler(CallbackQueryHandler(handle_confirm, pattern="confirm_send|cancel_send"))

# -- FastAPI Endpoint --
@app.post("/")
async def receive_update(request: Request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

if __name__ == "__main__":
    asyncio.run(main())