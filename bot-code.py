import time
import logging
import asyncio
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import uvicorn
import azure.functions as func

app = FastAPI()

TELEGRAM_BOT_TOKEN = "7798238582:AAFlDOPBn1qmrG8adDcUIn8OjoorTh7iBlI"

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

ADDRESS_FILE = "addresses.txt"
PAYMENT_LOGS_FILE = "payment_logs.txt"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler."""
    username = update.message.chat.username or "Unknown User"

    # Check if the user already has an address in the addresses file
    address_registered = False
    try:
        with open(ADDRESS_FILE, "r") as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith(f"{username} -"):
                    address_registered = True
                    break
    except FileNotFoundError:
        pass

    if not address_registered:
        context.user_data["expecting_address"] = True
        await update.message.reply_text("Welcome! Please enter your address to continue.")
    else:
        context.user_data["expecting_address"] = False
        keyboard = [
            [InlineKeyboardButton("Change address", callback_data="change_address")],
            [InlineKeyboardButton("Pay", callback_data="pay")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Welcome back! You already have an address registered. You can either change your address or proceed with the payment.",
            reply_markup=reply_markup
        )


async def save_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the user's address and show options to Pay or Change Address."""
    if not context.user_data.get("expecting_address", False):
        return

    username = update.message.chat.username or "Unknown User"
    address = update.message.text

    updated = False
    lines = []
    try:
        with open(ADDRESS_FILE, "r") as file:
            lines = file.readlines()
        with open(ADDRESS_FILE, "w") as file:
            for line in lines:
                if line.startswith(f"{username} -"):
                    file.write(f"{username} - {address}\n")
                    updated = True
                else:
                    file.write(line)
    except FileNotFoundError:
        pass

    if not updated:
        with open(ADDRESS_FILE, "a") as file:
            file.write(f"{username} - {address}\n")

    context.user_data["username"] = username
    context.user_data["address"] = address
    context.user_data["expecting_address"] = False

    keyboard = [
        [InlineKeyboardButton("Pay", callback_data="pay")],
        [InlineKeyboardButton("Change address", callback_data="change_address")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Address saved. Click 'Pay' to proceed or 'Change address' to enter a new address.",
                                    reply_markup=reply_markup)


async def change_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'Change address' button click."""
    context.user_data["expecting_address"] = True
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Please enter your new address.")


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'Pay' button click and log the payment."""
    username = context.user_data.get("username", "Unknown User")
    address = context.user_data.get("address", "No address provided")

    current_time = time.strftime("%Y%m%d%H%M%S", time.gmtime())

    last_payment_id = "000000000"
    try:
        with open(PAYMENT_LOGS_FILE, "r") as file:
            lines = file.readlines()
            if lines:
                last_line = lines[-1]
                last_payment_id = last_line.split("-")[-1]
    except FileNotFoundError:
        pass

    new_payment_id_number = int(last_payment_id) + 1
    new_payment_id = str(new_payment_id_number).zfill(9)
    payment_id = current_time + "-" + new_payment_id

    with open(PAYMENT_LOGS_FILE, "a") as file:
        file.write(f"{username}-{address}-{payment_id}\n")

    keyboard = [[InlineKeyboardButton("Start", callback_data="start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.answer()
    await update.callback_query.edit_message_text(f"Payment registered!\nPayment ID: {payment_id}",
                                                  reply_markup=reply_markup)


async def start_new_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'Start' button click to start a new session."""
    username = update.callback_query.message.chat.username or "Unknown User"

    address_registered = False
    try:
        with open(ADDRESS_FILE, "r") as file:
            lines = file.readlines()
            for line in lines:
                if line.startswith(f"{username} -"):
                    address_registered = True
                    break
    except FileNotFoundError:
        pass

    if not address_registered:
        context.user_data["expecting_address"] = True
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Welcome! Please enter your address to continue.")
    else:
        context.user_data["expecting_address"] = False
        keyboard = [
            [InlineKeyboardButton("Change address", callback_data="change_address")],
            [InlineKeyboardButton("Pay", callback_data="pay")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(
            "You already have an address registered. You can either change your address or proceed with the payment.",
            reply_markup=reply_markup
        )


# Add handlers
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_address))
telegram_app.add_handler(CallbackQueryHandler(change_address, pattern="^change_address$"))
telegram_app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
telegram_app.add_handler(CallbackQueryHandler(start_new_session, pattern="^start$"))


# Telegram Webhook
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


# Payment Callback Endpoints
@app.post("/success")
async def success_callback(request: Request):
    """Handle successful payments from IDBank."""
    try:
        data = await request.json()
        logging.info(f"Success Callback Data: {data}")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Error processing success callback: {e}")
        return {"status": "error"}


@app.post("/fail")
async def fail_callback(request: Request):
    """Handle failed payments from IDBank."""
    try:
        data = await request.json()
        logging.info(f"Fail Callback Data: {data}")
        return {"status": "failed"}
    except Exception as e:
        logging.error(f"Error processing fail callback: {e}")
        return {"status": "error"}


@app.get("/")
async def home():
    return {"message": "Telegram bot and payment system are running"}


async def run_bot():
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()


def start():
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    uvicorn.run(app, host="0.0.0.0", port=443)  # Use port 80 for Azure App Service


async def start_api():
    """Start FastAPI server."""
    config = uvicorn.Config(app, host="0.0.0.0", port=443, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Run Telegram bot and FastAPI server concurrently."""
    await asyncio.gather(start_api(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
