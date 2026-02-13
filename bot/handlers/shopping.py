from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db.storage import (
    add_to_shopping,
    get_shopping_list,
    remove_from_shopping,
)


# =====================================
# SAFE EDIT (решава text/caption проблема)
# =====================================
async def safe_edit(query, text, reply_markup=None):
    if query.message.text:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.edit_message_caption(text, reply_markup=reply_markup)


# =====================================
# ADD TO SHOPPING
# =====================================
async def add_to_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("add_shopping_", "")
    search_results = context.user_data.get("search_results", {})

    product = search_results.get(product_id)
    if not product:
        await safe_edit(query, "❌ Не може да се добави продукта.")
        return

    user_id = query.from_user.id
    added = add_to_shopping(user_id, product)

    text = (
        f"🛒 „{product['name']}“ е добавен в количката."
        if added
        else "ℹ️ Този продукт вече е в количката."
    )

    await safe_edit(query, text)


# =====================================
# LIST SHOPPING
# =====================================
async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    shopping = get_shopping_list(user_id)

    if not shopping:
        await safe_edit(query, "🛒 Количката е празна.")
        return

    text = "🛒 Твоята количка:\n\n"

    total_sum = 0
    store_totals = {}

    for i, product in enumerate(shopping, 1):
        price = float(product.get("price", 0))
        store = product.get("store", "Unknown")

        total_sum += price
        store_totals[store] = store_totals.get(store, 0) + price

        text += (
            f"{i}. {product['name']} "
            f"({store}) - {price:.2f}€\n"
        )

    # ========================
    # ОБЩА СУМА
    # ========================
    text += "\n"
    text += "💰 Обща сума: "
    text += f"{total_sum:.2f}€\n"

    # ========================
    # РАЗБИВКА ПО МАГАЗИН
    # ========================
    text += "\n🧾 Разбивка по магазини:\n"

    for store, store_sum in store_totals.items():
        text += f"• {store}: {store_sum:.2f}€\n"

    keyboard = [
        [InlineKeyboardButton("⬅️ Върни се в менюто", callback_data="main_menu")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit(query, text, reply_markup)

# =====================================
# REMOVE FROM SHOPPING
# =====================================
async def remove_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("remove_shopping_", "")
    user_id = query.from_user.id

    removed = remove_from_shopping(user_id, product_id)

    if not removed:
        await safe_edit(query, "❌ Продуктът вече не е в количката.")
        return

    await safe_edit(query, "🗑 Продуктът е премахнат от количката.")
