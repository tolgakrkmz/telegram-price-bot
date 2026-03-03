from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from db.repositories.history_repo import add_price_entry, get_product_history
from db.repositories.user_repo import (
    FREE_USER_DAILY_LIMIT,
    can_user_make_request,
    get_selected_stores,
    get_user_subscription_status,
    increment_request_count,
    is_user_premium,
)
from utils.helpers import calculate_unit_price, get_product_id
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

SEARCH_INPUT = 1
CURRENCY = "€"


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initializes search, checks limits and shows active filters."""
    user_id = update.effective_user.id

    if not is_user_premium(user_id) and not can_user_make_request(user_id):
        status = get_user_subscription_status(user_id)
        current_count = status.get("daily_request_count", 0) if status else 0
        limit_text = (
            f"🚫 *Limit Reached!* ({current_count}/{FREE_USER_DAILY_LIMIT})\n\n"
            f"Unlock *Unlimited* searches for only 2.50 EUR! 🚀"
        )
        if update.callback_query:
            await update.callback_query.answer(
                limit_text.replace("*", ""), show_alert=True
            )
            msg = await update.callback_query.message.reply_text(
                limit_text, parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            msg = await update.message.reply_text(
                limit_text, parse_mode=constants.ParseMode.MARKDOWN
            )
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    raw_stores = get_selected_stores(user_id)
    if isinstance(raw_stores, str):
        selected_stores = [s.strip() for s in raw_stores.split(",") if s.strip()]
    else:
        selected_stores = (
            [str(s).strip() for s in raw_stores] if raw_stores else ["all"]
        )

    store_info = (
        "All Stores 🌍" if "all" in selected_stores else ", ".join(selected_stores)
    )
    prompt_text = f"🔍 *Searching in:* {store_info}\n⌨️ *Enter the product name:*"

    if update.callback_query:
        await update.callback_query.answer()
        msg = await update.callback_query.message.reply_text(
            prompt_text, parse_mode=constants.ParseMode.MARKDOWN
        )
    else:
        msg = await update.message.reply_text(
            prompt_text, parse_mode=constants.ParseMode.MARKDOWN
        )

    add_message(user_id, msg.message_id)
    return SEARCH_INPUT


async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes input with store filters and handles caching."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    user_input = update.message.text.strip().lower()
    user_id = update.effective_user.id
    add_message(user_id, update.message.message_id)

    raw_stores = get_selected_stores(user_id)
    if isinstance(raw_stores, str):
        selected_stores = [s.strip() for s in raw_stores.split(",") if s.strip()]
    else:
        selected_stores = (
            [str(s).strip() for s in raw_stores] if raw_stores else ["all"]
        )

    from db.repositories.cache_repo import get_cached_results, set_cache_results

    cache_key = f"{user_input}:{','.join(sorted(selected_stores))}"
    products = get_cached_results(cache_key, expiry_hours=24)
    is_cached = True

    if not products:
        products = get_product_price(user_input, multiple=True, stores=selected_stores)
        is_cached = False
        if products:
            set_cache_results(cache_key, products)

    if not is_user_premium(user_id) or not is_cached:
        increment_request_count(user_id)

    if not products:
        msg = await update.message.reply_text(
            "❌ No products found in your selected stores.",
            reply_markup=main_menu_keyboard(user_id),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    for p in products:
        price_val = p.get("price_eur") or p.get("price")
        unit_val = p.get("quantity") or p.get("unit")
        u_price, u_unit = calculate_unit_price(price_val, unit_val)
        p["calc_unit_price"] = u_price
        p["base_unit"] = u_unit

        prod_id = get_product_id(p)
        store_info = p.get("supermarket")
        curr_store = (
            store_info.get("name")
            if isinstance(store_info, dict)
            else p.get("store", "Unknown")
        )

        try:
            add_price_entry(
                product_id=prod_id,
                name=p.get("name", "N/A"),
                store=curr_store,
                price=float(price_val) if price_val else 0.0,
                unit_price=u_price,
                base_unit=u_unit,
            )
        except Exception:
            pass

    products.sort(
        key=lambda x: (
            x["calc_unit_price"] if x["calc_unit_price"] is not None else float("inf")
        )
    )
    cheapest_unit_val = products[0]["calc_unit_price"] if products else None

    search_results = {}
    for p in products:
        product_id = get_product_id(p)
        search_results[product_id] = p

        curr_name = p.get("name", "N/A")
        curr_price = float(p.get("price_eur") or p.get("price", 0))
        store_info = p.get("supermarket")
        curr_store = (
            store_info.get("name")
            if isinstance(store_info, dict)
            else p.get("store", "Unknown")
        )
        curr_image = p.get("image_url") or p.get("image")

        history = get_product_history(product_id)
        trend_text = ""
        if history and len(history) > 1:
            try:
                prev_price = float(history[1]["price"])
                if curr_price < prev_price:
                    trend_text = f"📉 *Price drop!* (was {prev_price:.2f}{CURRENCY})\n"
                elif curr_price > prev_price:
                    trend_text = (
                        f"📈 *Price went up* (was {prev_price:.2f}{CURRENCY})\n"
                    )
            except:
                pass

        unit_price_info = ""
        best_value_tag = ""
        if p.get("calc_unit_price"):
            unit_price_info = f"⚖️ Unit Price: **{p['calc_unit_price']:.2f}{CURRENCY}/{p['base_unit']}**\n"
            if p["calc_unit_price"] == cheapest_unit_val:
                best_value_tag = "🏆 *BEST VALUE*\n"

        caption = (
            f"{best_value_tag}🛒 *{curr_name}*\n"
            f"💰 Price: **{curr_price:.2f}{CURRENCY}** ({p.get('quantity', 'n/a')})\n"
            f"{unit_price_info}🏬 Store: {curr_store}\n{trend_text}"
        )

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
                [
                    InlineKeyboardButton(
                        "📈 Price History", callback_data=f"price_history_{product_id}"
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
            add_message(user_id, msg.message_id)
        except:
            continue

    context.user_data["search_results"] = search_results

    nav_keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Search Again", callback_data="search"),
                InlineKeyboardButton(
                    "⚙️ Change Stores", callback_data="select_stores_menu"
                ),
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
    )

    final_msg = await update.message.reply_text(
        "✅ *Search completed!*",
        reply_markup=nav_keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    add_message(user_id, final_msg.message_id)

    return ConversationHandler.END
