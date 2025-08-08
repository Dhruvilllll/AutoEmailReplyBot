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