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
from contextlib import asynccontextmanager

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Register handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(
    CallbackQueryHandler(handle_choice, pattern="^(professional|casual|friendly)$")
)
telegram_app.add_handler(
    CallbackQueryHandler(handle_confirmation, pattern="^(confirm_send|cancel_send)$")
)

# ✅ Lifespan approach to handle startup (replaces @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_app.initialize()
    await telegram_app.start()
    asyncio.create_task(watch_emails(telegram_app))  # background task
    yield
    await telegram_app.stop()
    await telegram_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}
