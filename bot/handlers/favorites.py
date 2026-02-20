from telegram import Update
from telegram.ext import ContextTypes
from db.storage import add_favorite, remove_favorite, get_favorites
from utils.menu import main_menu_keyboard, favorites_keyboard  # Импортираме и двете менюта

async def add_to_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

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
        # Добавяме главното меню тук
        await query.message.edit_text(
            "⭐ Нямаш любими продукти.", 
            reply_markup=main_menu_keyboard()
        )
        return

    text = "⭐ Твоите любими продукти:\n\n"
    for i, (pid, p) in enumerate(favorites.items(), 1):
        if isinstance(p, dict):
            name = p.get('name', 'N/A')
            store = p.get('store', 'N/A')
            text += f"{i}. {name} ({store})\n"

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

    favorites = get_favorites(user_id)

    if favorites:
        text = "⭐ Твоите любими продукти:\n\n"
        for i, (pid, p) in enumerate(favorites.items(), 1):
            if isinstance(p, dict):
                name = p.get('name', 'N/A')
                store = p.get('store', 'N/A')
                text += f"{i}. {name} ({store})\n"
        await query.message.edit_text(text, reply_markup=favorites_keyboard(favorites))
    else:
        # И тук добавяме главното меню, ако изтрием последния продукт
        await query.message.edit_text(
            "⭐ Нямаш любими продукти.", 
            reply_markup=main_menu_keyboard()
        )