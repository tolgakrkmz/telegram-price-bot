from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

# Updated imports to use Supabase repository
from db.repositories.shopping_repo import (
    add_to_shopping_list as add_to_shopping,
    get_user_shopping_list as get_shopping_list,
    delete_shopping_item as remove_from_shopping,
    # Make sure this function exists in your shopping_repo.py
)
from db.storage import CACHE_FILE
from db.storage import _load_json as load_json
from utils.helpers import (
    calculate_unit_price,
    format_promo_dates,
)
from utils.menu import main_menu_keyboard

CURRENCY = "€"


def get_better_price(
    product_name: str,
    current_price: float,
    current_store: str,
    current_item: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Analyzes cached data to find better deals using EUR prices.
    """
    cache = load_json(CACHE_FILE)
    better_option = None

    curr_u_price, _ = calculate_unit_price(
        current_price, current_item.get("quantity") or current_item.get("unit")
    )

    if curr_u_price is None:
        return None

    min_unit_price = curr_u_price

    ignore_words = {
        "pilos",
        "саяна",
        "lidl",
        "kaufland",
        "billa",
        "боженци",
        "vereia",
        "верея",
    }
    keywords = [
        w for w in product_name.lower().split() if w not in ignore_words and len(w) > 2
    ]

    for query, data in cache.items():
        results = data if isinstance(data, list) else data.get("results", [])
        for p in results:
            p_name_lower = p.get("name", "").lower()
            match_count = sum(1 for word in keywords if word in p_name_lower)

            if match_count >= 2:
                try:
                    p_price = float(p.get("price_eur") or p.get("price", 0))
                    p_unit = p.get("quantity") or p.get("unit")

                    # Handle supermarket object or string
                    supermarket = p.get("supermarket")
                    p_store = (
                        supermarket.get("name")
                        if isinstance(supermarket, dict)
                        else p.get("store", "Unknown")
                    )

                    p_u_price, _ = calculate_unit_price(p_price, p_unit)

                    if (
                        p_u_price
                        and p_store != current_store
                        and p_u_price < min_unit_price
                    ):
                        if "%" in product_name:
                            percentage = [s for s in product_name.split() if "%" in s]
                            if percentage and percentage[0] not in p_name_lower:
                                continue

                        min_unit_price = p_u_price
                        better_option = {
                            "price": p_price,
                            "unit": p_unit,
                            "store": p_store,
                        }
                except (ValueError, TypeError, KeyError):
                    continue
    return better_option


async def safe_edit(
    query, text: str, reply_markup: InlineKeyboardMarkup = None
) -> None:
    """Safely updates messages with either text or caption."""
    params = {
        "text" if query.message.text else "caption": text,
        "reply_markup": reply_markup,
        "parse_mode": constants.ParseMode.MARKDOWN,
    }
    try:
        if query.message.text:
            await query.edit_message_text(**params)
        else:
            await query.edit_message_caption(**params)
    except Exception:
        pass


async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the shopping list from Supabase with EUR comparisons."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Fetch from Supabase instead of JSON
    shopping = get_shopping_list(user_id) or []

    if not shopping:
        text = "🛒 Your cart is empty."
        reply_markup = main_menu_keyboard(user_id)
        if query:
            await query.answer()
            await safe_edit(query, text, reply_markup)
        else:
            await update.message.reply_text(
                text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN
            )
        return

    if query:
        await query.answer()

    total_sum = 0.0
    potential_savings = 0.0
    store_totals: dict[str, float] = {}
    report_lines = ["🛒 *Your Shopping List*\n"]
    keyboard = []

    for product in shopping:
        price = float(product.get("price_eur") or product.get("price") or 0)

        # Handle supermarket field if it's a JSON/Dict
        supermarket = product.get("supermarket")
        store = (
            supermarket.get("name")
            if isinstance(supermarket, dict)
            else product.get("store", "Unknown")
        )

        name = product.get("name", "Unknown")
        unit = product.get("quantity") or product.get("unit", "N/A")

        # Use Supabase UUID for deletion
        db_id = product.get("id")

        total_sum += price
        store_totals[store] = store_totals.get(store, 0.0) + price

        promo_timer = format_promo_dates(product)
        promo_text = f" | ⏳ {promo_timer}" if promo_timer else ""

        better = get_better_price(name, price, store, product)
        better_text = ""
        if better:
            better_text = f"   💡 *Better Deal:* {better['price']:.2f}{CURRENCY} ({better['unit']}) at {better['store']}\n"
            if better.get("unit") == unit:
                potential_savings += price - float(better["price"])

        report_lines.append(
            f"• {name}\n   💰 **{price:.2f}{CURRENCY}** ({unit}){promo_text}\n   🏬 {store}\n{better_text}"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🗑 Remove {name[:15]}...",
                    callback_data=f"remove_shopping_{db_id}",
                )
            ]
        )

    summary = [
        f"\n📦 Items: {len(shopping)}",
        f"💰 *Total Sum: {total_sum:.2f}{CURRENCY}*",
    ]

    if potential_savings > 0:
        summary.append(f"✨ *Potential Savings: {potential_savings:.2f}{CURRENCY}*")

    summary.append("\n🧾 *By Store:*")
    for store, s_sum in store_totals.items():
        summary.append(f"• {store}: {s_sum:.2f}{CURRENCY}")

    report_lines.extend(summary)
    keyboard.append(
        [InlineKeyboardButton("🧹 Clear Cart", callback_data="confirm_clear")]
    )
    keyboard.append([InlineKeyboardButton("⬅️ Menu", callback_data="main_menu")])

    final_text = "\n".join(report_lines)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await safe_edit(query, final_text, reply_markup)
    else:
        await update.message.reply_text(
            final_text,
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN,
        )


async def add_to_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Adds a product to the Supabase shopping cart."""
    query = update.callback_query
    if not query:
        return

    product_id = query.data.replace("add_shopping_", "")
    search_results = context.user_data.get("search_results", {})
    product = search_results.get(product_id)

    if not product:
        await query.answer("❌ Product not found.")
        return

    user_id = query.from_user.id
    added = add_to_shopping(user_id, product)

    if added:
        await query.answer(f"🛒 {product['name']} added to cart!")
    else:
        await query.answer("❌ Error adding to cart.")

    current_keyboard = query.message.reply_markup.inline_keyboard
    new_keyboard = []

    for row in current_keyboard:
        new_row = []
        for button in row:
            if button.callback_data == query.data:
                new_row.append(InlineKeyboardButton("✅ In Cart", callback_data="none"))
            else:
                new_row.append(button)
        new_keyboard.append(new_row)

    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(new_keyboard)
        )
    except Exception:
        pass


async def remove_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Removes a single item using its Supabase UUID."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    item_uuid = query.data.replace("remove_shopping_", "")
    remove_from_shopping(item_uuid)
    await list_shopping(update, context)


async def confirm_clear_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="clear_shopping"),
            InlineKeyboardButton("❌ Cancel", callback_data="view_shopping"),
        ]
    ]
    await safe_edit(query, "⚠️ Clear the entire cart?", InlineKeyboardMarkup(keyboard))


async def clear_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Clears the entire shopping list for the user."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id

    # Import locally or ensure it's in the repo
    from db.repositories.shopping_repo import SHOPPING_TABLE, supabase

    try:
        supabase.table(SHOPPING_TABLE).delete().eq("user_id", user_id).execute()
    except Exception:
        pass

    await safe_edit(
        query, "🧹 Cart has been cleared.", reply_markup=main_menu_keyboard(user_id)
    )
