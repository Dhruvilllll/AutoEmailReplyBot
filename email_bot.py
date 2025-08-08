import os
import asyncio
import time
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv
import openai

load_dotenv()

import nest_asyncio
nest_asyncio.apply()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import AsyncOpenAI

# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# --- Globals ---
CURRENT_EMAIL = {}
DRAFT_REPLY = ""
start_time = int(time.time())  # capture launch time to avoid past mails

# --- Gmail Authentication ---
from io import StringIO
from pathlib import Path
import json

def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    elif os.path.exists('credentials.json'):
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    else:
        raise FileNotFoundError("credentials.json not found!")
    return build('gmail', 'v1', credentials=creds)


# --- Generate GPT-Based Draft ---
# --- Generate GPT-Based Draft ---
async def generate_gpt_reply(tone, sender, subject, snippet):
    prompt = f"""You are Dhruvil Malvania, a highly motivated and approachable B.Tech Computer Science Engineering student at Gandhinagar University, graduating in 2027. 
You write email replies based on the tone: Professional, Casual, Friendly. 
ALWAYS end the email with:
"Best regards,
Dhruvil Malvania"

Make sure to replace any placeholders like [YOUR_NAME] with your actual name.
Now draft a {tone} email reply to the following message:"""

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You're a smart email assistant who writes full, tone-specific replies ending with a proper signature."},
            {"role": "user", "content": f"{prompt}\nFrom: {sender}\nSubject: {subject}\nMessage: {snippet}"}
        ],
        max_tokens=300
    )

    reply = response.choices[0].message.content.strip()

    # Remove [YOUR_NAME] or similar placeholders if any
    for placeholder in ["[YOUR_NAME]", "<YOUR_NAME>", "{YOUR_NAME}"]:
        reply = reply.replace(placeholder, "Dhruvil Malvania")

    return reply

# --- Send Email ---
def send_email(service, to, subject, message_text, thread_id=None):
    message = MIMEText(message_text)
    message['to'] = to
    message['subject'] = "Re: " + subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw}
    if thread_id:
        body['threadId'] = thread_id
    service.users().messages().send(userId='me', body=body).execute()
    
# --- Telegram Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I'm your email assistant bot.\nI'll notify you of new emails and help you reply directly from Telegram.")

# --- Handle Tone Choice ---
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DRAFT_REPLY
    query = update.callback_query
    await query.answer()
    tone = query.data.lower()

    sender = CURRENT_EMAIL.get('sender', 'Unknown')
    subject = CURRENT_EMAIL.get('subject', '(No Subject)')
    snippet = CURRENT_EMAIL.get('snippet', '')

    DRAFT_REPLY = await generate_gpt_reply(tone, sender, subject, snippet)

    # Ask for confirmation
    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=f"💬 *{tone.title()}* reply draft:\n\n```\n{DRAFT_REPLY}\n```\n\nDo you want to send this?",
        parse_mode="Markdown"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
    ]
    await context.bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text="Please confirm your choice:",
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
        await query.edit_message_text("📤 Email sent successfully.")
    else:
        await query.edit_message_text("🚫 Email draft cancelled.")

# --- Email Monitoring ---
async def watch_emails(app):
    service = gmail_authenticate()

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

async def handle_webhook_update(update: Update, app):
    await app.process_update(update)

# --- Main ---
async def handler(request):
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="^(professional|casual|friendly)$"))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^(confirm_send|cancel_send)$"))

    asyncio.create_task(watch_emails(app))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return "Bot running"

from telegram.ext import Application

async def handle_webhook_update(update: Update, app):
    await app.process_update(update)
    