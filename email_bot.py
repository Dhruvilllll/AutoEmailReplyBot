# email_bot.py

import os
import time
import base64
import asyncio
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

import openai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import AsyncOpenAI

# ─── Configuration ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = int(os.getenv("TELEGRAM_CHAT_ID"))
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
openai.api_key     = OPENAI_API_KEY

SCOPES     = ['https://www.googleapis.com/auth/gmail.modify']
START_TIME = int(time.time())  # only fetch mails after launch
CURRENT_EMAIL = {}            # holds the last fetched email
DRAFT_REPLY   = ""            # holds the GPT draft

# ─── Gmail Authentication ──────────────────────────────────────────────────────

def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json','w') as f:
            f.write(creds.to_json())
    return build('gmail','v1', credentials=creds)

# ─── GPT‐Based Draft Generation ─────────────────────────────────────────────────

async def generate_gpt_reply(tone: str, sender: str, subject: str, snippet: str) -> str:
    prompt = (
        f"You are Dhruvil Malvania, a friendly yet professional B.Tech CSE student "
        f"(Gandhinagar Institute of Technology ’27). Draft a {tone} email reply "
        f"to this message, always ending with:\n\n"
        f"Best regards,\nDhruvil Malvania\n\n"
        f"Original message:\nFrom: {sender}\nSubject: {subject}\n\n{snippet}"
    )

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    resp = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role":"system","content":"You write concise, tone‐specific email replies."},
            {"role":"user","content": prompt}
        ],
        max_tokens=250
    )
    text = resp.choices[0].message.content.strip()
    # remove any leftover placeholders
    for ph in ["[YOUR_NAME]","<YOUR_NAME>","{YOUR_NAME}"]:
        text = text.replace(ph, "Dhruvil Malvania")
    return text

# ─── Send Email via Gmail API ──────────────────────────────────────────────────

def send_email(service, to: str, subject: str, body_text: str, thread_id: str = None):
    msg = MIMEText(body_text)
    msg['to']      = to
    msg['subject'] = "Re: " + subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    payload = {'raw': raw}
    if thread_id:
        payload['threadId'] = thread_id

    service.users().messages().send(userId='me', body=payload).execute()

# ─── Telegram Handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I’ll notify you of new emails and help you reply directly here."
    )

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DRAFT_REPLY
    q = update.callback_query
    await q.answer()
    tone = q.data  # "professional", "casual" or "friendly"

    sender  = CURRENT_EMAIL.get('sender', 'Unknown')
    subject = CURRENT_EMAIL.get('subject','(No Subject)')
    snippet = CURRENT_EMAIL.get('snippet','')

    DRAFT_REPLY = await generate_gpt_reply(tone, sender, subject, snippet)

    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            f"📝 *{tone.title()}* draft:\n\n"
            f"```{DRAFT_REPLY}```\n\n"
            f"Send it?"
        ),
        parse_mode="Markdown"
    )
    kb = [
        [InlineKeyboardButton("✅ Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
    ]
    await context.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="Please confirm:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    choice = q.data  # "confirm_send" or "cancel_send"

    if choice == "confirm_send":
        svc = gmail_authenticate()
        send_email(
            svc,
            CURRENT_EMAIL['sender'],
            CURRENT_EMAIL['subject'],
            DRAFT_REPLY,
            thread_id=CURRENT_EMAIL.get('threadId')
        )
        await q.edit_message_text("📤 Email sent!")
    else:
        await q.edit_message_text("🚫 Cancelled.")

# ─── Background Email Watcher ─────────────────────────────────────────────────

async def watch_emails(app):
    service = gmail_authenticate()
    while True:
        try:
            q = f"is:unread after:{START_TIME}"
            resp = service.users().messages().list(
                userId='me', labelIds=['INBOX'], q=q, maxResults=1
            ).execute()
            msgs = resp.get('messages',[])
            if msgs:
                msg = service.users().messages().get(
                    userId='me', id=msgs[0]['id']
                ).execute()

                hdrs   = msg['payload']['headers']
                sender = next(h['value'] for h in hdrs if h['name']=='From')
                subject= next(h['value'] for h in hdrs if h['name']=='Subject')
                snippet= msg.get('snippet','')

                # print to your terminal (Vercel logs)
                if "<" in sender and ">" in sender:
                    name = sender.split("<")[0].strip().strip('"')
                    eid  = sender.split("<")[1].strip(">")
                else:
                    name, eid = "Unknown", sender
                print(f"📥 New Email from {name} <{eid}> — {subject}")

                CURRENT_EMAIL.update({
                    'threadId': msg.get('threadId'),
                    'sender': sender,
                    'subject': subject,
                    'snippet': snippet
                })

                kb = [
                    [InlineKeyboardButton("Professional", callback_data="professional")],
                    [InlineKeyboardButton("Casual",       callback_data="casual")],
                    [InlineKeyboardButton("Friendly",     callback_data="friendly")],
                    [InlineKeyboardButton("Ignore",       callback_data="cancel_send")]
                ]
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=(
                        f"📬 *New Email!*\n"
                        f"*From:* {sender}\n"
                        f"*Subject:* {subject}\n"
                        f"*Snippet:* {snippet}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(kb)
                )

                service.users().messages().modify(
                    userId='me', id=msg['id'],
                    body={'removeLabelIds':['UNREAD']}
                ).execute()

        except HttpError as err:
            print("❌ Gmail API error:", err)
        except Exception as e:
            print("⚠️ watch_emails error:", e)

        await asyncio.sleep(20)
