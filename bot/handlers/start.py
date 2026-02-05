from telegram.ext import ContextTypes
from telegram import Update
from utils.menu import main_menu_keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добре дошли! Изберете опция от менюто:",
        reply_markup=main_menu_keyboard()
    )
