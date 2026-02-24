from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from db.repositories.cache_repo import (
    get_all_cached_products,
)

# Updated imports to use Supabase repository
from db.repositories.shopping_repo import (
    add_to_shopping_list as add_to_shopping,
)
from db.repositories.shopping_repo import (
    delete_shopping_item as remove_from_shopping,
)
from db.repositories.shopping_repo import (
    get_user_shopping_list as get_shopping_list,
)
from utils.helpers import calculate_unit_price
from utils.menu import main_menu_keyboard

CURRENCY = "€"


def get_better_price(
    product_name: str,
    current_price: float,
    current_store: str,
    current_item: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Analyzes Supabase cloud cache to find better deals using unit prices.
    """
    # Вместо load_json, взимаме всичко кеширано от Supabase
    all_cached_results = get_all_cached_products()
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

    for products in all_cached_results:
        for p in products:
            p_name_lower = p.get("name", "").lower()
            match_count = sum(1 for word in keywords if word in p_name_lower)

            if match_count >= 2:
                try:
                    p_price = float(p.get("price_eur") or p.get("price", 0))
                    p_unit = p.get("quantity") or p.get("unit")

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

    total_sum, potential_savings = 0.0, 0.0
    store_totals: dict[str, float] = {}
    report_lines = ["🛒 *Your Shopping List*\n"]
    keyboard = []

    for product in shopping:
        price = float(product.get("price_eur") or product.get("price") or 0)
        supermarket = product.get("supermarket")
        store = (
            supermarket.get("name")
            if isinstance(supermarket, dict)
            else product.get("store", "Unknown")
        )
        name = product.get("name", "Unknown")
        unit = product.get("quantity") or product.get("unit", "N/A")
        db_id = product.get("id")

        total_sum += price
        store_totals[store] = store_totals.get(store, 0.0) + price

        better = get_better_price(name, price, store, product)
        better_text = ""
        if better:
            better_text = f"   💡 *Better Deal:* {better['price']:.2f}{CURRENCY} ({better['unit']}) at {better['store']}\n"
            potential_savings += price - float(better["price"])

        report_lines.append(
            f"• {name}\n   💰 **{price:.2f}{CURRENCY}** ({unit})\n   🏬 {store}\n{better_text}"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🗑 Remove {name[:15]}...", callback_data=f"remove_shopping_{db_id}"
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

    await (
        safe_edit(query, "\n".join(report_lines), InlineKeyboardMarkup(keyboard))
        if query
        else update.message.reply_text(
            "\n".join(report_lines),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    )


async def add_to_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    product_id = query.data.replace("add_shopping_", "")
    product = context.user_data.get("search_results", {}).get(product_id)

    if not product:
        await query.answer("❌ Product not found.")
        return

    if add_to_shopping(query.from_user.id, product):
        await query.answer(f"🛒 {product['name']} added to cart!")
        new_keyboard = [
            [
                InlineKeyboardButton("✅ In Cart", callback_data="none")
                if b.callback_data == query.data
                else b
                for b in r
            ]
            for r in query.message.reply_markup.inline_keyboard
        ]
        try:
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(new_keyboard)
            )
        except:
            pass
    else:
        await query.answer("❌ Error adding to cart.")


async def remove_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    item_uuid = query.data.replace("remove_shopping_", "")
    remove_from_shopping(item_uuid)
    await list_shopping(update, context)


async def confirm_clear_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="clear_shopping"),
            InlineKeyboardButton("❌ Cancel", callback_data="view_shopping"),
        ]
    ]
    await safe_edit(
        update.callback_query,
        "⚠️ Clear the entire cart?",
        InlineKeyboardMarkup(keyboard),
    )


async def clear_shopping_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user_id = update.effective_user.id
    from db.repositories.shopping_repo import SHOPPING_TABLE, supabase

    try:
        supabase.table(SHOPPING_TABLE).delete().eq("user_id", user_id).execute()
    except:
        pass
    await safe_edit(
        update.callback_query,
        "🧹 Cart has been cleared.",
        reply_markup=main_menu_keyboard(user_id),
    )
