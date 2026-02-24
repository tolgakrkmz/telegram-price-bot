from collections import defaultdict
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.repositories.favorites_repo import (
    add_favorite,
    delete_favorite as remove_favorite,
    get_user_favorites,
)
from db.repositories.shopping_repo import add_to_shopping_list
from services.history_service import get_combined_price_history
from utils.helpers import calculate_unit_price, format_promo_dates
from utils.menu import favorites_keyboard, main_menu_keyboard

CURRENCY = "€"


# ==========================================================
# Render Favorites
# ==========================================================


async def render_favorites_text(favorites: dict) -> str:
    """Build formatted favorites message with live price data."""
    if not favorites:
        return "⭐ Your favorites list is empty."

    grouped = defaultdict(list)

    for pid, product in favorites.items():
        supermarket = product.get("supermarket")
        store_name = (
            supermarket.get("name")
            if isinstance(supermarket, dict)
            else product.get("store", "Unknown")
        )
        grouped[store_name].append((pid, product))

    text = "⭐ *Your Favorite Products:*\n\n"

    for store, products in grouped.items():
        text += f"🏪 *{store}*\n"

        for pid, product in products:
            name = product.get("name", "N/A")
            saved_price = float(product.get("price_eur") or product.get("price") or 0)
            unit = product.get("quantity") or product.get("unit", "")

            fresh_results = get_product_price(name, multiple=True) or []

            current_match = next(
                (
                    item
                    for item in fresh_results
                    if (
                        (item.get("supermarket") or {}).get("name") == store
                        or item.get("store") == store
                    )
                    and item.get("name") == name
                ),
                None,
            )

            current_price = saved_price
            promo_info = ""
            price_alert = ""

            if current_match:
                current_price = float(current_match.get("price_eur") or saved_price)

                api_old_price = current_match.get("old_price_eur")
                discount = current_match.get("discount")
                promo_timer = format_promo_dates(current_match)

                if promo_timer:
                    promo_info = f" | {promo_timer}"

                if current_price < saved_price:
                    price_alert = f" 🔥 *NOW {current_price:.2f}{CURRENCY}!*"

                if api_old_price:
                    discount_info = f" (-{discount}%)" if discount else ""
                    price_alert += (
                        f"\n   📉 *Promo:* Was {float(api_old_price):.2f}"
                        f"{CURRENCY}{discount_info}"
                    )

            unit_price, unit_label = calculate_unit_price(current_price, unit)
            unit_info = (
                f" | ⚖️ {unit_price:.2f}{CURRENCY}/{unit_label}" if unit_price else ""
            )

            text += (
                f" • {name}\n"
                f"   💰 **{current_price:.2f}{CURRENCY}**"
                f"{unit_info}{promo_info}{price_alert}\n"
            )

        text += "\n"

    return text


# ==========================================================
# List Favorites
# ==========================================================


async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Refreshing prices...")

    user_id = query.from_user.id
    fav_list = get_user_favorites(user_id) or []

    favorites = {
        str(item.get("product_id") or item.get("id")): item for item in fav_list
    }

    if not favorites:
        await query.message.edit_text(
            "⭐ Your favorites list is empty.",
            reply_markup=main_menu_keyboard(user_id),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    text = await render_favorites_text(favorites)

    await query.message.edit_text(
        text,
        reply_markup=favorites_keyboard(favorites),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ==========================================================
# Add Favorite
# ==========================================================


async def add_to_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    product_id = query.data.replace("add_favorite_", "")
    search_results = context.user_data.get("search_results", {})
    product = search_results.get(product_id)

    if not product:
        await query.answer("❌ Product not found.")
        return

    user_id = query.from_user.id
    added = add_favorite(user_id, product)

    if isinstance(added, dict) and not added.get("error"):
        await query.answer(f"⭐ {product['name']} added to favorites!")
    else:
        await query.answer("ℹ️ Already in favorites or error.")

    # Update button UI
    current_keyboard = query.message.reply_markup.inline_keyboard
    new_keyboard = []

    for row in current_keyboard:
        new_row = []
        for button in row:
            if button.callback_data == query.data:
                new_row.append(
                    InlineKeyboardButton("✅ In Favorites", callback_data="none")
                )
            else:
                new_row.append(button)
        new_keyboard.append(new_row)

    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(new_keyboard)
        )
    except Exception:
        pass


# ==========================================================
# Delete Favorite
# ==========================================================


async def delete_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("delete_", "")
    remove_favorite(query.from_user.id, product_id)

    await list_favorites(update, context)


# ==========================================================
# Move to Shopping Cart
# ==========================================================


async def move_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.replace("fav_to_cart_", "")
    fav_list = get_user_favorites(query.from_user.id) or []

    product = next(
        (item for item in fav_list if str(item.get("product_id")) == product_id),
        None,
    )

    if product:
        add_to_shopping_list(query.from_user.id, product)
        await query.answer(f"🛒 {product['name']} added to cart!")
    else:
        await query.answer("❌ Product not found.")


# ==========================================================
# View Price History
# ==========================================================


async def view_price_history_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer("Fetching price history...")

    product_id = query.data.replace("price_history_", "")
    user_id = query.from_user.id

    fav_list = get_user_favorites(user_id) or []
    product_entry = next(
        (p for p in fav_list if str(p.get("product_id")) == product_id),
        None,
    )

    if not product_entry:
        await query.message.reply_text("❌ Product not found.")
        return

    product_name = product_entry.get("name", "Product")
    store = product_entry.get("store", "Store")

    combined_history = get_combined_price_history(product_id, product_name, store)

    if not combined_history:
        await query.message.reply_text(
            f"❌ No historical data available for {product_name}."
        )
        return

    sorted_dates = sorted(combined_history.keys())

    lines = [f"📈 *Extended History for {product_name}*:\n"]

    for date in sorted_dates[-15:]:
        try:
            display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        except Exception:
            display_date = date

        lines.append(f"• {display_date}: **{combined_history[date]:.2f}{CURRENCY}**")

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
