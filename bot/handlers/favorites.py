from telegram import Update
from telegram.ext import ContextTypes
from db.storage import add_favorite, remove_favorite, get_favorites

async def add_to_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # callback_data = "add_favorite_<product_id>"
    product_id = query.data.replace("add_favorite_", "")
    search_results = context.user_data.get("search_results", {})

    product = search_results.get(product_id)
    if not product:
        await query.edit_message_text("❌ Не може да се добави продукта.")
        return

    user_id = query.from_user.id
    added = add_favorite(user_id, product)

    response_text = f"⭐ „{product['name']}“ е добавен в любими." if added else "ℹ️ Този продукт вече е в любими."

    if query.message.text:
        await query.edit_message_text(response_text)
    else:
        await query.edit_message_caption(response_text)


async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    favorites = get_favorites(user_id)

    if not favorites:
        await query.message.edit_text("⭐ Нямаш любими продукти.")
        return

    text = "⭐ Твоите любими продукти:\n\n"
    for i, (pid, p) in enumerate(favorites.items(), 1):
        text += f"{i}. {p['name']} ({p['store']})\n"

    from utils.menu import favorites_keyboard
    await query.message.edit_text(text, reply_markup=favorites_keyboard(favorites))


async def delete_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("delete_", "")
    user_id = query.from_user.id
    removed = remove_favorite(user_id, product_id)

    if not removed:
        await query.message.edit_text("❌ Продуктът вече не е в любими.")
        return

    # Обновяваме списъка с любими
    from db.storage import get_favorites
    favorites = get_favorites(user_id)
    from utils.menu import favorites_keyboard

    if favorites:
        text = "⭐ Твоите любими продукти:\n\n"
        for i, (pid, p) in enumerate(favorites.items(), 1):
            text += f"{i}. {p['name']} ({p['store']})\n"
        await query.message.edit_text(text, reply_markup=favorites_keyboard(favorites))
    else:
        await query.message.edit_text("⭐ Нямаш любими продукти.")
