import datetime
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.repositories.favorites_repo import (
    add_favorite,
)
from db.repositories.favorites_repo import (
    delete_favorite as remove_favorite,
)
from db.repositories.favorites_repo import (
    get_user_favorites as get_favorites,
)
from db.repositories.history_repo import get_product_history
from db.repositories.shopping_repo import add_to_shopping_list as add_to_shopping
from db.storage import HISTORY_FILE, _load_json
from utils.helpers import calculate_unit_price, format_promo_dates
from utils.menu import favorites_keyboard, main_menu_keyboard

CURRENCY = "€"


async def render_favorites_text(favorites: dict) -> str:
    """Displays favorites with live price updates and brochure dates."""
    if not favorites:
        return "⭐ Your favorites list is empty."

    grouped_favorites = defaultdict(list)
    for pid, p in favorites.items():
        supermarket = p.get("supermarket")
        store_name = (
            supermarket.get("name")
            if isinstance(supermarket, dict)
            else p.get("store", "Unknown")
        )
        grouped_favorites[store_name].append((pid, p))

    text = "⭐ *Your Favorite Products:*\n\n"

    for store, products in grouped_favorites.items():
        text += f"🏪 *{store}*\n"
        for pid, p in products:
            name = p.get("name", "N/A")
            saved_price = float(p.get("price_eur") or p.get("price") or 0)
            unit = p.get("quantity") or p.get("unit", "")

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

            price_alert = ""
            current_price = saved_price
            promo_timer = ""

            if current_match:
                current_price = float(current_match.get("price_eur") or saved_price)
                api_old_price = current_match.get("old_price_eur")
                discount = current_match.get("discount")
                promo_timer = format_promo_dates(current_match)

                if current_price < saved_price:
                    price_alert = f" 🔥 *NOW {current_price:.2f}{CURRENCY}!*"

                if api_old_price:
                    discount_info = f" (-{discount}%)" if discount else ""
                    price_alert += f"\n   📉 *Promo:* Was {float(api_old_price):.2f}{CURRENCY}{discount_info}"

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
    fav_list = get_favorites(user_id) or []

    favorites = {}
    for item in fav_list:
        pid = str(item.get("product_id") or item.get("id"))
        favorites[pid] = item

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


async def add_to_favorite_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
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


async def delete_favorite_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = query.data.replace("delete_", "")
    remove_favorite(query.from_user.id, product_id)
    await list_favorites(update, context)


async def move_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    product_id = query.data.replace("fav_to_cart_", "")

    fav_list = get_favorites(query.from_user.id) or []
    product = next(
        (item for item in fav_list if str(item.get("product_id")) == product_id), None
    )

    if product:
        add_to_shopping(query.from_user.id, product)
        await query.answer(f"🛒 {product['name']} added to cart!")
    else:
        await query.answer("❌ Error: Product not found.")


async def view_price_history_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Shows history by combining API data and Supabase records."""
    query = update.callback_query
    product_id = query.data.replace("price_history_", "")

    await query.answer("Fetching price history...")

    # 1. Get history from Supabase (using our repository)
    db_records = get_product_history(product_id)

    product_entry = None
    if not db_records:
        # Fallback to favorites to get product info for API search
        user_id = query.from_user.id
        from db.repositories.favorites_repo import get_user_favorites

        favs = get_user_favorites(user_id)
        product_entry = next(
            (p for p in favs if str(p.get("product_id")) == product_id), None
        )
    else:
        # Use the latest DB record to get name and store
        product_entry = db_records[0]

    if not product_entry and not db_records:
        await query.message.reply_text("❌ Product history details not found.")
        return

    product_name = product_entry.get("name", "Product")
    store = product_entry.get("store", "Store")

    # 2. Fetch extended history from API
    api_results = get_product_price(product_name, multiple=True) or []
    api_match = next(
        (
            p
            for p in api_results
            if (
                p.get("store") == store
                or (p.get("supermarket") or {}).get("name") == store
            )
            and p.get("name") == product_name
        ),
        None,
    )

    # 3. Combine both sources
    combined_history = {}

    # Add API history (usually YYYY-MM-DD format)
    if api_match and "history" in api_match:
        for entry in api_match["history"]:
            combined_history[entry["date"]] = float(entry["price"])

    # Add Supabase history (using recorded_date)
    for entry in db_records:
        # Try 'recorded_date' first, then fallback to 'recorded_at' just in case
        date_val = entry.get("recorded_date") or entry.get("recorded_at")

        if date_val:
            # Format to YYYY-MM-DD if it's a timestamp string
            date_str = str(date_val).split("T")[0]
            combined_history[date_str] = float(entry["price"])

    sorted_dates = sorted(combined_history.keys())

    if not sorted_dates:
        await query.message.reply_text(
            f"❌ No historical data available for {product_name}."
        )
        return

    # 4. Format Output
    history_lines = [f"📈 *Extended History for {product_name}*:\n"]

    # Show last 15 entries
    for date in sorted_dates[-15:]:
        # Optional: Format date from YYYY-MM-DD to DD.MM.YYYY for better readability
        try:
            display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
        except:
            display_date = date
        history_lines.append(
            f"• {display_date}: **{combined_history[date]:.2f}{CURRENCY}**"
        )

    if api_match and "history" in api_match:
        history_lines.append("\n_Includes data from supermarket archives_")

    await query.message.reply_text(
        "\n".join(history_lines), parse_mode=constants.ParseMode.MARKDOWN
    )
