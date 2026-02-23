from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from db.storage import (
    get_cached_search,
    get_product_history,
    save_search_to_cache,
    update_price_history,
)
from utils.helpers import calculate_unit_price, get_product_id
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

# Constants
SEARCH_INPUT = 1
CURRENCY = "€"


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initializes the search process and prompts for user input."""
    prompt_text = "🔍 Enter the product name:"
    user_id = update.effective_user.id

    if update.message:
        msg = await update.message.reply_text(prompt_text)
        add_message(user_id, msg.message_id)
    elif update.callback_query:
        await update.callback_query.answer()
        msg = await update.callback_query.message.reply_text(prompt_text)
        add_message(user_id, msg.message_id)

    return SEARCH_INPUT


async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes search input, handles caching, compares unit prices, and displays results."""
    user_input = update.message.text.strip()
    user_id = update.effective_user.id

    products = get_cached_search(user_input)
    is_cached = True

    if not products:
        products = get_product_price(user_input, multiple=True)
        if products:
            save_search_to_cache(user_input, products)
        is_cached = False

    if not products:
        msg = await update.message.reply_text("❌ No products found.")
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    for p in products:
        price_val = p.get("price_eur") or p.get("price")
        unit_val = p.get("quantity") or p.get("unit")
        u_price, u_unit = calculate_unit_price(price_val, unit_val)
        p["calc_unit_price"] = u_price
        p["base_unit"] = u_unit

    products.sort(
        key=lambda x: (
            x["calc_unit_price"] if x["calc_unit_price"] is not None else float("inf")
        )
    )
    cheapest_unit_val = products[0]["calc_unit_price"] if products else None

    search_results = {}
    messages_to_cache = []

    for p in products:
        product_id = get_product_id(p)
        
        # --- DATES LOGIC FOR NOTIFICATIONS ---
        promo_timer = ""
        brochure = p.get("brochure")
        if brochure and isinstance(brochure, dict):
            from_d = brochure.get("valid_from")
            until_d = brochure.get("valid_until")
            
            # Map valid_until to valid-until for storage consistency
            if until_d:
                p["valid-until"] = until_d
                
            if from_d and until_d:
                try:
                    f = datetime.strptime(from_d, "%Y-%m-%d").strftime("%d.%m")
                    u = datetime.strptime(until_d, "%Y-%m-%d").strftime("%d.%m")
                    promo_timer = f"⏳ {f} - {u}"
                except:
                    promo_timer = f"⏳ {from_d} - {until_d}"

        # Store product in session results
        search_results[product_id] = p

        curr_name = p.get("name", "N/A")
        curr_price = p.get("price_eur") or p.get("price", 0)
        curr_store = (
            p.get("supermarket", {}).get("name")
            if isinstance(p.get("supermarket"), dict)
            else p.get("store", "Unknown")
        )
        curr_unit = p.get("quantity") or p.get("unit", "")
        curr_image = p.get("image_url") or p.get("image")

        if not is_cached:
            update_price_history(product_id, curr_price, curr_name, curr_store)

        history = get_product_history(product_id)
        trend_text = ""
        if len(history) > 1:
            try:
                prev_price = float(history[-2]["price"])
                if float(curr_price) < prev_price:
                    trend_text = f"📉 Price drop! (was {prev_price:.2f}{CURRENCY})\n"
            except:
                pass

        unit_price_info = ""
        best_value_tag = ""
        if p.get("calc_unit_price"):
            unit_price_info = f"⚖️ Unit Price: **{p['calc_unit_price']:.2f}{CURRENCY}/{p['base_unit']}**\n"
            if p["calc_unit_price"] == cheapest_unit_val:
                best_value_tag = "🏆 *BEST VALUE*\n"

        promo_info = f" | {promo_timer}" if promo_timer else ""

        caption = (
            f"{best_value_tag}"
            f"🛒 *{curr_name}*\n"
            f"💰 Price: **{float(curr_price):.2f}{CURRENCY}** ({curr_unit}){promo_info}\n"
            f"{unit_price_info}"
            f"🏬 Store: {curr_store}\n"
            f"{trend_text}"
        )

        if p.get("discount"):
            caption += f"💸 Discount: {p['discount']}%\n"

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⭐ Add to Favorites",
                        callback_data=f"add_favorite_{product_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🛒 Add to Cart", callback_data=f"add_shopping_{product_id}"
                    )
                ],
            ]
        )

        try:
            if curr_image:
                msg = await update.message.reply_photo(
                    curr_image,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            else:
                msg = await update.message.reply_text(
                    caption,
                    reply_markup=keyboard,
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
            messages_to_cache.append(msg.message_id)
        except:
            continue

    context.user_data["search_results"] = search_results
    footer_text = "✅ Search completed!" + (" (cached data)" if is_cached else "")
    
    # FIXED: Added user_id to main_menu_keyboard to avoid TypeError
    final_msg = await update.message.reply_text(
        footer_text, reply_markup=main_menu_keyboard(user_id)
    )
    
    messages_to_cache.append(final_msg.message_id)
    for m_id in messages_to_cache:
        add_message(user_id, m_id)
    return ConversationHandler.END