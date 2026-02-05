from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔥 Оферти днес", callback_data="deals")],
        [InlineKeyboardButton("🔍 Търси продукт", callback_data="search")],
        [InlineKeyboardButton("⭐ Любими", callback_data="favorites")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🛒 Добре дошъл!\n\n"
        "С този бот можеш да намираш най-добрите цени и оферти в супермаркетите.",
        reply_markup=reply_markup
    )
