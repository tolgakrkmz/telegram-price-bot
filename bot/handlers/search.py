from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from api.supermarket import get_product_price
from utils.menu import main_menu_keyboard
from utils.helpers import get_product_id
from utils.message_cache import add_message
# Импортираме новите функции от storage
from db.storage import get_cached_search, save_search_to_cache, update_price_history, get_product_history

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
    user_id = update.effective_user.id

    # 1. Проверка в кеша (Пестим от лимита 50 заявки)
    cached_products = get_cached_search(user_input)
    
    if cached_products:
        products = cached_products
        is_cached = True
    else:
        # 2. Ако няма кеш, викаме API-то
        products = get_product_price(user_input, multiple=True)
        if products:
            save_search_to_cache(user_input, products)
        is_cached = False

    if not products:
        msg = await update.message.reply_text("❌ Няма намерен продукт.")
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    search_results = {}
    messages_to_cache = []

    for p in products:
        product_id = get_product_id(p)
        search_results[product_id] = p
        
        # 3. Записваме в историята на цените (само ако данните са пресни от API)
        if not is_cached:
            update_price_history(product_id, p['price'], p['name'], p['store'])

        # 4. Проверяваме историята за този продукт, за да покажем тренд
        history = get_product_history(product_id)
        trend_text = ""
        if len(history) > 1:
            old_price = history[-2]['price'] # Предишната записана цена
            current_price = float(p['price'])
            if current_price < old_price:
                trend_text = f"📉 Намаление! (беше {old_price} лв)\n"
            elif current_price > old_price:
                trend_text = f"📈 Поскъпване! (беше {old_price} лв)\n"

        msg_text = (
            f"🛒 {p['name']}\n"
            f"💰 Цена: {p['price']} лв / {p['unit']}\n"
            f"🏬 Магазин: {p['store']}\n"
            f"{trend_text}" # Тук се добавя инфото за историята
        )
        if p.get("discount"):
            msg_text += f"💸 Намаление: {p['discount']}%\n"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ Добави в любими", callback_data=f"add_favorite_{product_id}")],
            [InlineKeyboardButton("🛒 Добави в количката", callback_data=f"add_shopping_{product_id}")]
        ])

        if p.get("image"):
            msg = await update.message.reply_photo(p["image"], caption=msg_text, reply_markup=keyboard)
        else:
            msg = await update.message.reply_text(msg_text, reply_markup=keyboard)

        messages_to_cache.append(msg.message_id)

    context.user_data["search_results"] = search_results

    final_msg = await update.message.reply_text(
        "✅ Готово!" + (" (данни от кеш)" if is_cached else ""),
        reply_markup=main_menu_keyboard()
    )
    messages_to_cache.append(final_msg.message_id)

    for msg_id in messages_to_cache:
        add_message(user_id, msg_id)

    return ConversationHandler.END