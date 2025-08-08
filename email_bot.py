# email_bot.py
import os
import base64
import time
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

import openai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

openai.api_key = os.getenv("OPENAI_API_KEY")

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CURRENT_EMAIL = {}

def gmail_authenticate():
    creds = None
    from pathlib import Path

    creds_path = Path("credentials.json")
    if not creds_path.exists():
        base64_creds = os.getenv("GMAIL_CREDENTIALS_BASE64")
        if base64_creds:
            decoded_creds = base64.b64decode(base64_creds).decode("utf-8")
            creds_path.write_text(decoded_creds)
            print("✅ credentials.json created from environment variable.")
        else:
            print("❌ GMAIL_CREDENTIALS_BASE64 not set.")
            return None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)

async def generate_gpt_reply(tone, sender, subject, snippet):
    prompt = f"""You are Dhruvil Malvania, a motivated and approachable B.Tech Computer Science Engineering student.
Write a {tone} reply. ALWAYS end with:
Best regards,
Dhruvil Malvania
No [YOUR_NAME] placeholders."""

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a smart email assistant."},
            {"role": "user", "content": f"{prompt}\nFrom: {sender}\nSubject: {subject}\nMessage: {snippet}"}
        ],
        max_tokens=300
    )
    reply = response.choices[0].message.content.strip()
    for ph in ["[YOUR_NAME]", "<YOUR_NAME>", "{YOUR_NAME}"]:
        reply = reply.replace(ph, "Dhruvil Malvania")
    return reply

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
