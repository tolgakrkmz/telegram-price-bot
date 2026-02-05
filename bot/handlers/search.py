from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from api.supermarket import get_product_price

SEARCH_INPUT = 1

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        await update.message.reply_text("🔍 Въведи името на продукта:")
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("🔍 Въведи името на продукта:")
    return SEARCH_INPUT

async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    products = get_product_price(user_input, multiple=True)

    if not products:
        await update.message.reply_text("❌ Няма намерен продукт.")
    else:
        for p in products:
            msg = (
                f"🛒 {p['name']}\n"
                f"💰 Цена: {p['price']} лв / {p['unit']}\n"
                f"🏬 Магазин: {p['store']}\n"
            )
            if p.get("discount"):
                msg += f"💸 Намаление: {p['discount']}%\n"
            if p.get("image"):
                await update.message.reply_photo(p['image'], caption=msg)
            else:
                await update.message.reply_text(msg)

    return ConversationHandler.END

def get_search_keyboard():
    keyboard = [[InlineKeyboardButton("🔎 Търси продукт", callback_data="search_product")]]
    return InlineKeyboardMarkup(keyboard)
