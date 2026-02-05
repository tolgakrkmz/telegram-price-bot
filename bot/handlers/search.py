from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
from api.supermarket import get_product_price
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

SEARCH_INPUT = 1

async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        msg = await update.message.reply_text("🔍 Въведи името на продукта:")
        add_message(update.effective_user.id, msg.message_id)
    elif update.callback_query:
        await update.callback_query.answer()
        msg = await update.callback_query.message.reply_text("🔍 Въведи името на продукта:")
        add_message(update.effective_user.id, msg.message_id)
    return SEARCH_INPUT

async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    products = get_product_price(user_input, multiple=True)

    messages_to_cache = []

    if not products:
        # няма намерен продукт
        msg = await update.message.reply_text(
            "❌ Няма намерен продукт."
        )
        messages_to_cache.append(msg.message_id)
    else:
        for p in products:
            msg_text = (
                f"🛒 {p['name']}\n"
                f"💰 Цена: {p['price']} лв / {p['unit']}\n"
                f"🏬 Магазин: {p['store']}\n"
            )
            if p.get("discount"):
                msg_text += f"💸 Намаление: {p['discount']}%\n"

            if p.get("image"):
                msg = await update.message.reply_photo(p['image'], caption=msg_text)
            else:
                msg = await update.message.reply_text(msg_text)

            messages_to_cache.append(msg.message_id)

    final_msg = await update.message.reply_text(
        "✅ Готово! Изберете опция от менюто:",
        reply_markup=main_menu_keyboard()
    )
    messages_to_cache.append(final_msg.message_id)

    from utils.message_cache import add_message
    for msg_id in messages_to_cache:
        add_message(update.effective_user.id, msg_id)

    return ConversationHandler.END
