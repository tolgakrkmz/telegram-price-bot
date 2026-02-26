from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from db.repositories.shopping_repo import get_user_shopping_list
from db.repositories.cache_repo import get_all_cached_products
from db.repositories.user_repo import is_user_premium
from services.optimizer import ShoppingOptimizer

CURRENCY = "€"


async def premium_cart_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main entry point for the Premium Smart Cart experience."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_user_premium(user_id):
        await query.answer("💎 This is a Premium feature!", show_alert=True)
        return

    shopping_list = get_user_shopping_list(user_id)
    if not shopping_list:
        await query.answer("🛒 Your cart is empty.")
        return

    market_cache = get_all_cached_products()
    optimizer = ShoppingOptimizer(shopping_list, market_cache)
    split_plan = optimizer.get_smart_split_plan()

    text = (
        "💎 *Smart Shopping Mode*\n"
        "--------------------------\n"
        f"📦 Items in cart: {len(shopping_list)}\n"
        f"💰 Current Total: {split_plan['total_original']:.2f}{CURRENCY}\n\n"
        "Choose your optimization strategy:"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                f"🚀 Smart Split (-{split_plan['savings']:.2f}{CURRENCY})",
                callback_data="opt_split",
            )
        ],
        [InlineKeyboardButton("🏠 Cheapest Single Store", callback_data="opt_single")],
        [
            InlineKeyboardButton("📝 Export List", callback_data="premium_export"),
            InlineKeyboardButton("⬅️ Back", callback_data="view_shopping"),
        ],
    ]

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_smart_split(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer("Processing Smart Plan...")

    shopping_list = get_user_shopping_list(user_id)
    market_cache = get_all_cached_products()
    optimizer = ShoppingOptimizer(shopping_list, market_cache)
    plan = optimizer.get_smart_split_plan()

    report = ["💎 *Smart Cart Plan*\n"]
    report.append("💡 _Optimal route for your current list:_\n")

    for store, items in plan["stores"].items():
        report.append(f"🏪 *STORE: {store.upper()}*")

        # Group items to avoid duplicate rows
        store_summary = {}
        for item in items:
            name = item["name"]
            if name not in store_summary:
                store_summary[name] = {"count": 0, "total": 0.0, "price": item["price"]}
            store_summary[name]["count"] += 1
            store_summary[name]["total"] += item["price"]

        for name, data in store_summary.items():
            if data["count"] > 1:
                # Cleaner representation of multiple items
                report.append(
                    f"• {name} (*{data['count']} pcs*) — *{data['total']:.2f}{CURRENCY}*"
                )
            else:
                report.append(f"• {name} — *{data['price']:.2f}{CURRENCY}*")

        report.append("")

    report.append("---")
    report.append(f"💰 *TOTAL SUM: {plan['total_optimized']:.2f}{CURRENCY}*")
    report.append(f"🎉 *TOTAL SAVINGS: {plan['savings']:.2f}{CURRENCY}*")

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="premium_cart")]]

    await query.edit_message_text(
        text="\n".join(report),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_single_store(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer("Optimizing for single store...")

    shopping_list = get_user_shopping_list(user_id)
    market_cache = get_all_cached_products()
    optimizer = ShoppingOptimizer(shopping_list, market_cache)
    best_option = optimizer.get_single_store_plan()

    if not best_option:
        await query.answer("No store data found.")
        return

    report = [
        "💎 *Smart Cart: Single Store Choice*\n",
        f"🏆 *WINNER:* {best_option['store'].upper()}",
        f"💰 *Total for found items:* {best_option['total']:.2f}{CURRENCY}\n",
        "✅ *Items available at this store:*",
    ]

    # Group found items
    found_summary = {}
    for item in best_option["found_items"]:
        name = item["name"]
        found_summary[name] = found_summary.get(name, 0) + 1

    for name, count in found_summary.items():
        qty = f" ({count} pcs)" if count > 1 else ""
        report.append(f"• {name}{qty}")

    # Show missing items separately
    if best_option["missing_items"]:
        report.append("\n⚠️ *Not found at this store:*")
        missing_names = set(item["name"] for item in best_option["missing_items"])
        for name in missing_names:
            report.append(f"• _{name}_")

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="premium_cart")]]

    await query.edit_message_text(
        text="\n".join(report),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
