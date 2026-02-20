from telegram.ext import ContextTypes
from telegram import Update
from utils.menu import main_menu_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Добре дошли! Изберете опция от менюто:"

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=main_menu_keyboard()
        )

    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.message.edit_text(
            text,
            reply_markup=main_menu_keyboard()
        )
