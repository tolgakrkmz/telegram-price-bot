from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from db.repositories.history_repo import add_price_entry, get_product_history
from db.repositories.user_repo import (
    get_user_subscription_status,
    increment_request_count,
    is_user_premium,
    can_user_make_request,
    FREE_USER_DAILY_LIMIT,
)
from utils.helpers import calculate_unit_price, get_product_id
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

SEARCH_INPUT = 1
CURRENCY = "€"


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initializes the search process and checks if the user has reached their daily limit."""
    user_id = update.effective_user.id

    # Check if the user is allowed to perform a search
    if not can_user_make_request(user_id):
        status = get_user_subscription_status(user_id)
        current_count = status.get("daily_request_count", 0) if status else 0

        limit_text = (
            f"🚫 *Limit Reached!* ({current_count}/{FREE_USER_DAILY_LIMIT})\n\n"
            f"Unlock *Unlimited* searches and Premium features for only 2.50 BGN! 🚀"
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

    prompt_text = "🔍 *Enter the product name:*"

    if update.message:
        msg = await update.message.reply_text(
            prompt_text, parse_mode=constants.ParseMode.MARKDOWN
        )
        add_message(user_id, msg.message_id)
    elif update.callback_query:
        await update.callback_query.answer()
        msg = await update.callback_query.message.reply_text(
            prompt_text, parse_mode=constants.ParseMode.MARKDOWN
        )
        add_message(user_id, msg.message_id)

    return SEARCH_INPUT


async def search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes search input, manages limits, and displays results."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    user_input = update.message.text.strip().lower()
    user_id = update.effective_user.id

    add_message(user_id, update.message.message_id)

    from db.repositories.cache_repo import get_cached_results, set_cache_results

    # 1. Data Retrieval
    products = get_cached_results(user_input, expiry_hours=24)
    is_cached = True

    if not products:
        products = get_product_price(user_input, multiple=True)
        is_cached = False
        if products:
            set_cache_results(user_input, products)

    # 2. Limit Logic
    is_premium = is_user_premium(user_id)
    if not is_premium or not is_cached:
        increment_request_count(user_id)

    if not products:
        msg = await update.message.reply_text("❌ No promotional products found.")
        add_message(user_id, msg.message_id)
        return ConversationHandler.END

    # 3. Unit Price Calculation & Global History Logging
    for p in products:
        # Calculate pricing details
        price_val = p.get("price_eur") or p.get("price")
        unit_val = p.get("quantity") or p.get("unit")
        u_price, u_unit = calculate_unit_price(price_val, unit_val)
        p["calc_unit_price"] = u_price
        p["base_unit"] = u_unit

        # Prepare data for history
        prod_id = get_product_id(p)
        store_info = p.get("supermarket")
        curr_store = (
            store_info.get("name")
            if isinstance(store_info, dict)
            else p.get("store", "Unknown")
        )

        # MANDATORY LOGGING: Save every product returned by API to history
        add_price_entry(
            product_id=prod_id,
            name=p.get("name", "N/A"),
            store=curr_store,
            price=float(price_val) if price_val else 0.0,
            unit_price=u_price,
            base_unit=u_unit,
        )

    # 4. Sorting for UI
    products.sort(
        key=lambda x: (
            x["calc_unit_price"] if x["calc_unit_price"] is not None else float("inf")
        )
    )
    cheapest_unit_val = products[0]["calc_unit_price"] if products else None

    # 5. UI Rendering Loop
    search_results = {}
    for p in products:
        product_id = get_product_id(p)
        promo_timer = ""
        brochure = p.get("brochure")

        if brochure and isinstance(brochure, dict):
            until_d = brochure.get("valid_until")
            from_d = brochure.get("valid_from")
            if until_d:
                p["valid-until"] = until_d
            if from_d and until_d:
                try:
                    f = datetime.strptime(from_d, "%Y-%m-%d").strftime("%d.%m")
                    u = datetime.strptime(until_d, "%Y-%m-%d").strftime("%d.%m")
                    promo_timer = f"⏳ {f} - {u}"
                except:
                    promo_timer = f"⏳ {from_d} - {until_d}"

        search_results[product_id] = p
        curr_name = p.get("name", "N/A")
        curr_price = float(p.get("price_eur") or p.get("price", 0))

        # Supermarket name for caption
        store_info = p.get("supermarket")
        curr_store = (
            store_info.get("name")
            if isinstance(store_info, dict)
            else p.get("store", "Unknown")
        )

        curr_unit = p.get("quantity") or p.get("unit", "")
        curr_image = p.get("image_url") or p.get("image")

        # Fetch history for trend visualization
        history = get_product_history(product_id)
        trend_text = ""
        if history and len(history) > 1:
            try:
                prev_price = float(history[1]["price"])
                if curr_price < prev_price:
                    diff = prev_price - curr_price
                    trend_text = f"📉 *Price drop!* (was {prev_price:.2f}{CURRENCY}, saved {diff:.2f}{CURRENCY})\n"
                elif curr_price > prev_price:
                    trend_text = (
                        f"📈 *Price went up* (was {prev_price:.2f}{CURRENCY})\n"
                    )
            except (IndexError, ValueError, KeyError):
                pass

        # Caption formatting
        unit_price_info = ""
        best_value_tag = ""
        if p.get("calc_unit_price"):
            unit_price_info = f"⚖️ Unit Price: **{p['calc_unit_price']:.2f}{CURRENCY}/{p['base_unit']}**\n"
            if p["calc_unit_price"] == cheapest_unit_val:
                best_value_tag = "🏆 *BEST VALUE*\n"

        promo_info = f" | {promo_timer}" if promo_timer else ""
        caption = (
            f"{best_value_tag}🛒 *{curr_name}*\n"
            f"💰 Price: **{curr_price:.2f}{CURRENCY}** ({curr_unit}){promo_info}\n"
            f"{unit_price_info}🏬 Store: {curr_store}\n{trend_text}"
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
        except Exception as e:
            print(f"Error sending message: {e}")
            continue

    context.user_data["search_results"] = search_results
    status_label = " (cloud cache)" if is_cached else " (fresh data)"
    final_msg = await update.message.reply_text(
        f"✅ *Search completed!*{status_label}",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    add_message(user_id, final_msg.message_id)
    return ConversationHandler.END
