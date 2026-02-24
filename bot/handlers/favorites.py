from collections import defaultdict
from datetime import datetime

# Fixed import to use your client
from db.supabase_client import supabase
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.repositories.favorites_repo import (
    add_favorite,
    get_user_favorites,
)
from db.repositories.favorites_repo import (
    delete_favorite as remove_favorite,
)
from db.repositories.history_repo import get_product_history
from db.repositories.user_repo import is_user_premium  # Imported for limit checks
from db.repositories.shopping_repo import add_to_shopping_list
from services.history_service import get_combined_price_history
from utils.helpers import calculate_unit_price, format_promo_dates
from utils.menu import favorites_keyboard, main_menu_keyboard

CURRENCY = "€"
FREE_FAVORITES_LIMIT = 3

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

    user_id = query.from_user.id
    is_premium = is_user_premium(user_id)  # Synchronous check
    fav_list = get_user_favorites(user_id) or []

    # --- ENHANCED LIMIT CHECK (SHOW ALERT) ---
    if not is_premium and len(fav_list) >= FREE_FAVORITES_LIMIT:
        limit_text = (
            f"⭐ Favorites Limit! ({len(fav_list)}/{FREE_FAVORITES_LIMIT})\n\n"
            "Upgrade to Premium for only 2.50 EUR to unlock:\n"
            "• Unlimited Favorites\n"
            "• Price Drop Alerts\n"
            "• Price History & Smart Shopping! 🚀"
        )
        await query.answer(limit_text, show_alert=True)
        return
    # ------------------------------------------

    product_id = query.data.replace("add_favorite_", "")
    search_results = context.user_data.get("search_results", {})
    product = search_results.get(product_id)

    if not product:
        await query.answer("❌ Product not found.")
        return

    added = add_favorite(user_id, product)

    if isinstance(added, dict) and not added.get("error"):
        await query.answer(f"⭐ {product['name']} added to favorites!")

        # Update button UI to show confirmation
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
    else:
        await query.answer("ℹ️ Already in favorites or error.")


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

    # Improved lookup to handle both UUID and product_id
    product = next(
        (
            item
            for item in fav_list
            if str(item.get("product_id")) == product_id
            or str(item.get("id")) == product_id
        ),
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
) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if not is_user_premium(user_id):
        await query.answer("⭐ Premium Feature Only", show_alert=True)
        return

    await query.answer()
    raw_id = query.data.replace("price_history_", "").strip()

    product_data = None

    # 1. Try search results cache
    search_results = context.user_data.get("search_results", {})
    product_data = search_results.get(raw_id)

    # 2. Try Favorites DB lookup (UUID or product_id)
    if not product_data:
        try:
            res = (
                supabase.table("favorites")
                .select("*")
                .or_(f"id.eq.{raw_id},product_id.eq.{raw_id}")
                .execute()
            )
            if res.data:
                product_data = res.data[0]
        except:
            pass

    # 3. Fetch history using all available identifiers
    history = []
    ids_to_try = list(
        filter(None, [raw_id, product_data.get("product_id") if product_data else None])
    )

    for pid in set(ids_to_try):
        res = (
            supabase.table("price_history").select("*").eq("product_id", pid).execute()
        )
        if res.data:
            history = res.data
            break

    # 4. Critical Fallback: Search by Name if IDs failed
    if not history and product_data and product_data.get("name"):
        try:
            res_name = (
                supabase.table("price_history")
                .select("*")
                .ilike("name", product_data["name"])
                .execute()
            )
            history = res_name.data
        except:
            pass

    if not history:
        await query.message.reply_text("📉 No history found for this item.")
        return

    # Sort and Display
    history.sort(key=lambda x: x.get("recorded_date", ""), reverse=True)

    name = (
        product_data.get("name") if product_data else history[0].get("name", "Product")
    )
    store = (
        product_data.get("store") if product_data else history[0].get("store", "Store")
    )

    text = f"📊 *Price History*\n🛒 *{name}*\n🏬 {store}\n\n"

    seen_dates = set()
    for entry in history:
        d = entry.get("recorded_date", "N/A")
        if d not in seen_dates:
            seen_dates.add(d)
            price = float(entry.get("price", 0))
            text += f"• {d}: **{price:.2f}{CURRENCY}**\n"

    await query.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)


def get_all_favorites_from_db():
    try:
        response = supabase.table("favorites").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching all favorites: {e}")
        return []
