from collections import defaultdict

from telegram import Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.storage import (
    HISTORY_FILE,
    _load_json,  # Imported to access the full history object if needed
    add_favorite,
    add_to_shopping,
    get_favorites,
    remove_favorite,
)
from utils.helpers import calculate_unit_price, format_promo_dates
from utils.menu import favorites_keyboard, main_menu_keyboard

CURRENCY = "€"


async def render_favorites_text(favorites: dict) -> str:
    """Displays favorites with live price updates and brochure dates."""
    if not favorites:
        return "⭐ Your favorites list is empty."

    grouped_favorites = defaultdict(list)
    for pid, p in favorites.items():
        # Fallback for store name
        store_name = (
            p.get("supermarket", {}).get("name")
            if isinstance(p.get("supermarket"), dict)
            else p.get("store", "Unknown")
        )
        grouped_favorites[store_name].append((pid, p))

    text = "⭐ *Your Favorite Products:*\n\n"
    _load_json(HISTORY_FILE)

    for store, products in grouped_favorites.items():
        text += f"🏪 *{store}*\n"
        for pid, p in products:
            name = p.get("name", "N/A")
            # Always favor price_eur, fallback to price
            saved_price = float(p.get("price_eur") or p.get("price", 0))
            unit = p.get("quantity") or p.get("unit", "")

            # 1. Live Check via API
            fresh_results = get_product_price(name, multiple=True) or []
            current_match = next(
                (
                    item
                    for item in fresh_results
                    if (
                        item.get("supermarket", {}).get("name") == store
                        or item.get("store") == store
                    )
                    and item["name"] == name
                ),
                None,
            )

            price_alert = ""
            current_price = saved_price
            promo_timer = ""

            if current_match:
                current_price = float(current_match.get("price_eur", saved_price))
                api_old_price = current_match.get("old_price_eur")
                discount = current_match.get("discount")
                promo_timer = format_promo_dates(current_match)

                # Compare EUR with EUR
                if current_price < saved_price:
                    price_alert = f" 🔥 *NOW {current_price:.2f}{CURRENCY}!*"

                if api_old_price:
                    discount_info = f" (-{discount}%)" if discount else ""
                    price_alert += f"\n   📉 *Promo:* Was {float(api_old_price):.2f}{CURRENCY}{discount_info}"

            # 2. UI Construction
            u_price, u_unit = calculate_unit_price(current_price, unit)
            unit_info = f" | ⚖️ {u_price:.2f}{CURRENCY}/{u_unit}" if u_price else ""
            promo_info = f" | {promo_timer}" if promo_timer else ""

            text += f" • {name}\n   💰 **{current_price:.2f}{CURRENCY}**{unit_info}{promo_info}{price_alert}\n"
        text += "\n"

    return text


async def list_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the favorites list with all smart features."""
    query = update.callback_query
    await query.answer("Refreshing prices and history...")

    user_id = query.from_user.id
    favorites = get_favorites(user_id)

    if not favorites:
        await query.message.edit_text(
            "⭐ Your favorites list is empty.",
            reply_markup=main_menu_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    text = await render_favorites_text(favorites)
    await query.message.edit_text(
        text,
        reply_markup=favorites_keyboard(favorites),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def view_price_history_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    Shows history by combining API data (up to 30 days) and local records.
    """
    query = update.callback_query
    product_id = query.data.replace("price_history_", "")

    # 1. Get local history first
    full_history = _load_json(HISTORY_FILE)
    product_entry = full_history.get(product_id)

    if not product_entry:
        await query.answer("Product not found in local records.", show_alert=True)
        return

    await query.answer("Fetching extended history from API...")

    product_name = product_entry.get("name", "Product")
    store = product_entry.get("store", "Store")

    # 2. Fetch fresh data from API to get their 30-day historical data
    # Assuming your get_product_price or a similar function can return historical points
    api_results = get_product_price(product_name, multiple=True) or []

    # Try to find the specific product from this store in the API response
    api_match = next(
        (p for p in api_results if p["store"] == store and p["name"] == product_name),
        None,
    )

    # Build a dictionary to keep unique dates only (prefer API for external data)
    combined_history = {}

    # 3. Add API historical data if available (Assuming API provides 'history' key)
    # If the API returns a list of history, we map it here:
    if api_match and "history" in api_match:
        for entry in api_match["history"]:
            combined_history[entry["date"]] = float(entry["price"])

    # 4. Merge with our local history (overwrites API if dates overlap)
    for entry in product_entry.get("prices", []):
        combined_history[entry["date"]] = float(entry["price"])

    # 5. Sort by date and format
    sorted_dates = sorted(combined_history.keys())

    if not sorted_dates:
        await query.message.reply_text(
            "❌ No historical data available for this product yet."
        )
        return

    history_lines = [f"📈 *Extended History for {product_name}*:\n"]

    # Display the last 15 points (combination of API and local)
    for date in sorted_dates[-15:]:
        history_lines.append(f"• {date}: **{combined_history[date]:.2f}{CURRENCY}**")

    # Add a note if it's external data
    if api_match and "history" in api_match:
        history_lines.append("\n_Includes data from supermarket archives (30 days)_")

    await query.message.reply_text(
        "\n".join(history_lines), parse_mode=constants.ParseMode.MARKDOWN
    )


async def add_to_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.replace("add_favorite_", "")
    search_results = context.user_data.get("search_results", {})
    product = search_results.get(product_id)
    if not product:
        await query.message.reply_text("❌ Product data not found.")
        return
    user_id = query.from_user.id
    added = add_favorite(user_id, product)
    msg = (
        f"⭐ *{product['name']}* added to favorites."
        if added
        else "ℹ️ Already in favorites."
    )
    await query.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)


async def delete_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.replace("delete_", "")
    remove_favorite(query.from_user.id, product_id)
    await list_favorites(update, context)


async def move_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    product_id = query.data.replace("fav_to_cart_", "")
    favorites = get_favorites(query.from_user.id)
    product = favorites.get(product_id)
    if product:
        add_to_shopping(query.from_user.id, product)
        await query.answer(f"🛒 {product['name']} added to cart!")
    else:
        await query.answer("❌ Error: Product not found.")
