from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db.storage import (
    add_to_shopping,
    get_shopping_list,
    remove_from_shopping,
)


async def add_to_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("add_shopping_", "")
    search_results = context.user_data.get("search_results", {})

    product = search_results.get(product_id)
    if not product:
        await query.edit_message_text("❌ Не може да се добави продукта.")
        return

    user_id = query.from_user.id
    added = add_to_shopping(user_id, product)

    text = (
        f"🛒 „{product['name']}“ е добавен в количката."
        if added
        else "ℹ️ Този продукт вече е в количката."
    )

    if query.message.text:
        await query.edit_message_text(text)
    else:
        await query.edit_message_caption(text)


async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    shopping = get_shopping_list(user_id)

    if not shopping:
        await query.message.edit_text("🛒 Количката е празна.")
        return

    text = "🛒 Твоята количка:\n\n"
    for i, (pid, p) in enumerate(shopping.items(), 1):
        text += f"{i}. {p['name']} ({p['store']}) - {p['price']}€\n"

    keyboard = [[InlineKeyboardButton("⬅️ Върни се в менюто", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text(text, reply_markup=reply_markup)


async def remove_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("remove_shopping_", "")
    user_id = query.from_user.id

    removed = remove_from_shopping(user_id, product_id)

    if not removed:
        await query.message.edit_text("❌ Продуктът вече не е в количката.")
        return

    await query.message.edit_text("🗑 Продуктът е премахнат от количката.")
