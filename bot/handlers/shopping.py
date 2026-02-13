from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from handlers.start import start
from db.storage import (
    add_to_shopping,
    get_shopping_list,
    remove_from_shopping,
    clear_shopping_list,
)

# =============================
# SAFE EDIT
# =============================
async def safe_edit(query, text, reply_markup=None):
    if query.message.text:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.edit_message_caption(text, reply_markup=reply_markup)


# =============================
# ADD TO SHOPPING
# =============================
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
        else "ℹ️ Продуктът вече е в количката."
    )

    await safe_edit(query, text)


# =============================
# LIST SHOPPING (UX VERSION)
# =============================
async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    shopping = get_shopping_list(user_id)

    if not shopping:
        await safe_edit(query, "🛒 Количката е празна.")
        await start(update, context)
        return

    total_sum = 0
    store_totals = {}

    text = "🛒 *Твоята количка*\n\n"

    keyboard = []

    for i, product in enumerate(shopping, 1):
        price = float(product.get("price", 0))
        store = product.get("store", "Unknown")
        product_id = product.get("id")

        total_sum += price
        store_totals[store] = store_totals.get(store, 0) + price

        text += f"{i}. {product['name']}\n   🏬 {store} | 💶 {price:.2f}€\n\n"

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {i}",
                callback_data=f"remove_shopping_{product_id}"
            )
        ])

    text += f"📦 Брой продукти: {len(shopping)}\n"
    text += f"💰 Обща сума: {total_sum:.2f}€\n\n"

    text += "🧾 *По магазини:*\n"
    for store, store_sum in store_totals.items():
        text += f"• {store}: {store_sum:.2f}€\n"

    keyboard.append([
        InlineKeyboardButton("🧹 Изчисти количката", callback_data="confirm_clear")
    ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Меню", callback_data="main_menu")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit(query, text, reply_markup)


# =============================
# REMOVE PRODUCT
# =============================
async def remove_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("remove_shopping_", "")
    user_id = query.from_user.id

    remove_from_shopping(user_id, product_id)

    await list_shopping(update, context)


# =============================
# CONFIRM CLEAR
# =============================
async def confirm_clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="clear_shopping"),
            InlineKeyboardButton("❌ Отказ", callback_data="view_shopping"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit(query, "⚠️ Сигурна ли си, че искаш да изчистиш количката?", reply_markup)


# =============================
# CLEAR SHOPPING
# =============================
async def clear_shopping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    clear_shopping_list(user_id)

    await safe_edit(query, "🧹 Количката беше изчистена.")
