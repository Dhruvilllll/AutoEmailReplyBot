import os
import base64
import time
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from openai import AsyncOpenAI

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
start_time = int(time.time())

CURRENT_EMAIL = {}
DRAFT_REPLY = ""


def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


async def generate_gpt_reply(tone, sender, subject, snippet):
    prompt = f"""You are Dhruvil Malvania, a highly motivated and approachable B.Tech Computer Science Engineering student at Gandhinagar University, graduating in 2027. 
You write email replies based on the tone: Professional, Casual, Friendly. 
ALWAYS end the email with:
"Best regards,
Dhruvil Malvania"

Make sure to replace any placeholders like [YOUR_NAME] with your actual name.
Now draft a {tone} email reply to the following message:
From: {sender}
Subject: {subject}
Content: {snippet}"""

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Write respectful, tone-specific email replies."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=250
    )
    content = response.choices[0].message.content.strip()
    return f"{content}\n\nBest regards,\nDhruvil Malvania"


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
