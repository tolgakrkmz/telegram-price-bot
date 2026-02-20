from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from handlers.start import start
from db.storage import (
    add_to_shopping,
    get_shopping_list,
    remove_from_shopping,
    clear_shopping_list,
    load_json,
    CACHE_FILE
)

# =============================
# SMART PRICE COMPARISON
# =============================
def get_better_price(product_name, current_price, current_store, current_item):
    cache = load_json(CACHE_FILE)
    better_option = None
    
    # Вземаме единичната цена на текущия продукт
    # Ако API-то не дава unit_price, използваме общата като резервен вариант
    curr_unit_price = float(current_item.get('unit_price', current_price))
    min_unit_price = curr_unit_price

    for query, data in cache.items():
        results = data.get("results", [])
        for p in results:
            # 1. Проверка за подобно име
            if product_name.lower() in p['name'].lower() or p['name'].lower() in product_name.lower():
                try:
                    p_unit_price = float(p.get('unit_price', p['price']))
                    p_store = p['store']
                    
                    # 2. Сравняваме само ако е различен магазин и единичната цена е по-ниска
                    if p_store != current_store and p_unit_price < min_unit_price:
                        # 3. Важна проверка: Дали са еднакви мерни единици (бр. с бр., кг с кг)
                        if p.get('unit') == current_item.get('unit'):
                            min_unit_price = p_unit_price
                            better_option = p
                except (ValueError, TypeError):
                    continue
    return better_option

# =============================
# SAFE EDIT
# =============================
async def safe_edit(query, text, reply_markup=None):
    if query.message and query.message.text:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif query.message:
        await query.edit_message_caption(text, reply_markup=reply_markup, parse_mode="Markdown")


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
# LIST SHOPPING (SMART UX VERSION)
# =============================
async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    shopping = get_shopping_list(user_id)

    if not shopping:
        if query:
            await safe_edit(query, "🛒 Количката е празна.")
            await start(update, context)
        return

    total_sum = 0
    potential_savings = 0
    store_totals = {}
    text = "🛒 *Твоята количка*\n\n"
    keyboard = []

    for i, product in enumerate(shopping, 1):
        price = float(product.get("price", 0))
        store = product.get("store", "Unknown")
        name = product.get("name", "Unknown")
        product_id = product.get("id")

        total_sum += price
        store_totals[store] = store_totals.get(store, 0) + price

        # Проверка за по-добра цена
        better = get_better_price(name, price, store, product)
        
        better_text = ""
        if better:
            savings = price - float(better['price'])
            potential_savings += savings
            better_text = f"   💡 *По-добре:* {better['price']} лв в {better['store']}\n"

        text += f"{i}. {name}\n   🏬 {store} | 💶 {price:.2f}лв\n{better_text}\n"

        keyboard.append([
            InlineKeyboardButton(f"🗑 Премахни {i}", callback_data=f"remove_shopping_{product_id}")
        ])

    text += f"📦 Брой продукти: {len(shopping)}\n"
    text += f"💰 *Обща сума: {total_sum:.2f}лв*\n"
    
    if potential_savings > 0:
        text += f"✨ *Можеш да спестиш: {potential_savings:.2f}лв*\n"

    text += "\n🧾 *По магазини:*\n"
    for store, store_sum in store_totals.items():
        text += f"• {store}: {store_sum:.2f}лв\n"

    keyboard.append([InlineKeyboardButton("🧹 Изчисти количката", callback_data="confirm_clear")])
    keyboard.append([InlineKeyboardButton("⬅️ Меню", callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await safe_edit(query, text, reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


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