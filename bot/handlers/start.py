from telegram.ext import ContextTypes
from telegram import Update
from utils.menu import main_menu_keyboard

async def start(update, context):
    user_name = update.effective_user.first_name
    welcome_text = (
        f"👋 Hello, {user_name}!\n\n"
        "I am your personal grocery assistant. I help you compare prices between "
        "major supermarkets and save money automatically."
    )
    await update.message.reply_text(welcome_text)
    await update.message.reply_text("🏠 Main Menu:", reply_markup=main_menu_keyboard())
