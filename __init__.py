import logging
import azure.functions as func
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application

import os

# Initialize FastAPI app
app = FastAPI()

# Telegram bot token from environment variable
TELEGRAM_BOT_TOKEN = os.getenv("7798238582:AAFlDOPBn1qmrG8adDcUIn8OjoorTh7iBlI")

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Error processing update: {e}")
        return {"status": "error"}

@app.post("/success")
async def success_callback(request: Request):
    """Handle successful payments."""
    data = await request.json()
    logging.info(f"Success Callback Data: {data}")
    return {"status": "success"}

@app.post("/fail")
async def fail_callback(request: Request):
    """Handle failed payments."""
    data = await request.json()
    logging.info(f"Fail Callback Data: {data}")
    return {"status": "failed"}

# Azure Function entry point
async def main(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("Telegram bot and payment system are running", status_code=200)
