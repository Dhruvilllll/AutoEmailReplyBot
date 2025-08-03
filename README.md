# 🤖 Auto Email Reply Telegram Bot

An intelligent assistant that automatically notifies you of new unread emails and helps you generate personalized replies directly through Telegram using OpenAI GPT.

## ✨ Features

- 📥 Notifies you instantly on Telegram when a new email arrives.
- 💬 Lets you choose your reply tone: `Professional`, `Casual`, `Friendly`, or `Ignore`.
- 🧠 Uses OpenAI GPT to generate customized replies based on your tone.
- 👀 Shows you the drafted reply before sending — asks for your approval.
- 📤 Sends the reply from your Gmail account in one tap via Telegram.
- 🔒 Only new emails after bot startup are processed — older unread ones are skipped.

---

## ⚙️ Tech Stack

- **Language:** Python 3.11+
- **Email:** Gmail API (`google-api-python-client`)
- **AI:** OpenAI GPT (via `openai.AsyncOpenAI`)
- **Bot Framework:** `python-telegram-bot`
- **Deployment:** Not deployed as still working on it
- **Secrets Management:** `.env` using `python-dotenv`

---

## 🚀 How It Works

1. **Bot watches Gmail inbox** for new unread emails (after the time of startup).
2. **When a new email arrives**, you get a Telegram message with sender, subject, and a snippet.
3. You choose a reply tone via buttons:
   - 🧑‍💼 Professional
   - 😎 Casual
   - 😊 Friendly
   - ❌ Ignore
4. **GPT generates a reply** using your style, tone, and email content.
5. You confirm the draft — if approved, it is **sent directly via Gmail API**.

---

## 📁 Project Structure

AutoEmailReplyBot/

│

├── bot_watcher.py # Main logic for watching Gmail and handling Telegram interaction

├── credentials.json # Google API client credentials (OAuth)

├── token.json # Generated Gmail OAuth token after first login

├── .env # Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY

├── render.yaml # Configuration for Render deployment (optional)

├── requirements.txt # Python dependencies

└── README.md (You're here!)

## 👤 Author
Dhruvil Malvania

B.Tech CSE @ Gandhinagar University | AI/ML & Data Science Enthusiast

