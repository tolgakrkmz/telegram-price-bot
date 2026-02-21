from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes
from utils.menu import main_menu_keyboard

async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the bot guide and features."""
    query = update.callback_query
    await query.answer()

    info_text = (
        "🤖 *Smart Price Assistant - Guide*\n\n"
        "1️⃣ **Search:** Find products in Lidl & Kaufland. All prices are automatically converted to **€**.\n\n"
        "2️⃣ **Smart Cart:** When you add items, the bot automatically scans for a *better deal* in other stores based on unit prices.\n\n"
        "3️⃣ **Auto-Alerts:** The bot checks your ⭐ *Favorites* every morning at 09:00 and notifies you of price drops.\n\n"
        "4️⃣ **Global Sync:** We update prices efficiently to save your daily API limits and keep data fresh.\n\n"
        "💡 *Tip:* Use the manual 'Update' button in the Favorites menu if you want a real-time check right now!"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use edit_text because we are coming from a button click
    await query.message.edit_text(
        text=info_text,
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )