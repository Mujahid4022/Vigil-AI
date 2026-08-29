"""
telegram_bot.py - Telegram bot integration for Vigil AI.
Allows users to check status and trigger posts via Telegram.
"""

import os
import json
import time
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Global reference to the bot instance
BOT_APP = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Vigil AI Bot is alive!\n\n"
        "Commands:\n"
        "/status - Check bot status\n"
        "/post - Trigger a test post on all pages\n"
        "/pause - Pause the bot\n"
        "/resume - Resume the bot\n"
        "/pages - List connected Facebook pages"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from run import BOT_PAUSED
    status_text = "🔴 PAUSED" if BOT_PAUSED else "🟢 RUNNING"
    await update.message.reply_text(f"Bot status: {status_text}")

async def pages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    CONFIG_FILE = "config.json"
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        pages = config.get("pages", [])
        if pages:
            msg = "📋 **Your Pages:**\n"
            for p in pages:
                msg += f"- ID: {p['id']} | Interval: {p['interval']}h\n"
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("No pages configured.")
    else:
        await update.message.reply_text("Config not found.")

async def trigger_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Triggering test post...")
    try:
        from run import load_config, run_engine_1, run_engine_2
        config = load_config()
        pages = config.get("pages", [])
        for idx, p in enumerate(pages):
            if idx % 2 == 0:
                run_engine_1(p)
            else:
                run_engine_2(p)
        await update.message.reply_text("✅ Test posts triggered!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from run import BOT_PAUSED
    import run
    run.BOT_PAUSED = True
    await update.message.reply_text("⏸️ Bot paused.")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from run import BOT_PAUSED
    import run
    run.BOT_PAUSED = False
    await update.message.reply_text("▶️ Bot resumed.")

def start_telegram_bot(token):
    """Starts the Telegram bot in a background thread."""
    global BOT_APP
    if not token:
        print("⚠️ No Telegram token provided. Bot not started.")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("pages", pages))
    application.add_handler(CommandHandler("post", trigger_post))
    application.add_handler(CommandHandler("pause", pause))
    application.add_handler(CommandHandler("resume", resume))

    BOT_APP = application

    def run_polling():
        application.run_polling()

    thread = threading.Thread(target=run_polling, daemon=True)
    thread.start()
    print("✅ Telegram bot started in background.")