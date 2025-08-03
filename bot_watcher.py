import os
import base64
import asyncio
import time
from email.mime.text import MIMEText
from dotenv import load_dotenv
load_dotenv()
import nest_asyncio
nest_asyncio.apply()

import openai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

import json
with open("credentials.json", "r") as f:
    print(json.dumps(json.load(f)))

# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
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

    # Step 1: Decode base64 credentials and write to file if missing
    creds_path = Path("credentials.json")
    if not creds_path.exists():
        base64_creds = os.getenv("GMAIL_CREDENTIALS_BASE64")
        if base64_creds:
            try:
                decoded_creds = base64.b64decode(base64_creds).decode("utf-8")
                creds_path.write_text(decoded_creds)
                print("✅ credentials.json created from environment variable.")
            except Exception as e:
                print(f"❌ Failed to decode credentials: {e}")
                return None
        else:
            print("❌ GMAIL_CREDENTIALS_BASE64 not set in environment.")
            return None

    # Step 2: Perform authentication
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())

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
    try:
        message = MIMEText(message_text)
        message['to'] = to
        message['subject'] = "Re: " + subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        body = {'raw': raw}
        if thread_id:
            body['threadId'] = thread_id

        sent = service.users().messages().send(userId='me', body=body).execute()
        print(f"✅ Email sent to {to}, ID: {sent['id']}")
    except HttpError as error:
        print(f"❌ Failed to send email: {error}")

# --- Telegram Bot Commands ---
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
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_choice, pattern="professional|casual|friendly|ignore"))
    app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="confirm_send|cancel_send"))

    print("🚀 Bot started. Watching for new emails...")
    asyncio.create_task(watch_emails())
    await app.run_polling()

    print("🚀 Bot started. Watching for new emails...")
    asyncio.create_task(watch_emails())

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        webhook_url=f"https://{RENDER_EXTERNAL_URL}/webhook"
    )

if __name__ == "__main__":
    asyncio.run(main())