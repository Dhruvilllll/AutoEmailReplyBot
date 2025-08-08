from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler
from email_bot import (
    TELEGRAM_BOT_TOKEN,
    start,
    handle_choice,
    handle_confirmation,
    watch_emails
)
import asyncio

app = FastAPI()
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(handle_choice, pattern="^(professional|casual|friendly)$"))
telegram_app.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^(confirm_send|cancel_send)$"))

# Start background email watcher
@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    await telegram_app.start()
    asyncio.create_task(watch_emails(telegram_app))

@app.post("/")
async def handle(request: Request):
    body = await request.json()
    update = Update.de_json(body, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
