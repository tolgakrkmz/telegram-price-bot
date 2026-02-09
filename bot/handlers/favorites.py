from telegram import Update
from telegram.ext import ContextTypes
from db.storage import add_favorite, get_favorites

async def add_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_name = context.user_data.get("last_product")
    user_id = query.from_user.id

    if not product_name:
        if query.message.text:
            await query.edit_message_text("❌ Няма продукт за добавяне.")
        else:
            await query.edit_message_caption("❌ Няма продукт за добавяне.")
        return

    added = add_favorite(user_id, product_name)

    text = f"⭐ „{product_name}“ е добавен в любими." if added else "ℹ️ Този продукт вече е в любими."

    if query.message.text:
        await query.edit_message_text(text)
    else:
        await query.edit_message_caption(text)

async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    favorites = get_favorites(user_id)

    if not favorites:
        await update.message.reply_text("⭐ Нямаш любими продукти.")
        return

    text = "⭐ Твоите любими продукти:\n\n"
    for i, p in enumerate(favorites, 1):
        text += f"{i}. {p}\n"

    await update.message.reply_text(text)
