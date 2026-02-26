from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Core imports from your project
from api.supermarket import get_product_price
from db.repositories.cache_repo import (
    get_all_cached_products,
    get_cached_results,
    set_cache_results,
)
from services.optimizer import ShoppingOptimizer

SB_INPUT, SB_PREFERENCE = range(2)
CURRENCY = "€"


async def smart_basket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text(
        "✨ *Smart Basket Mode*\n\n"
        "Send your shopping list. You can use commas or new lines.\n"
        "Example:\n_eggs, butter, milk, yogurt_",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SB_INPUT


async def handle_sb_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    # Extract items and clean them
    items = [i.strip() for i in user_text.replace("\n", ",").split(",") if i.strip()]

    if not items:
        await update.message.reply_text("List is empty. Please try again.")
        return SB_INPUT

    context.user_data["sb_list"] = items

    keyboard = [
        [InlineKeyboardButton("🌍 Any Store (Split All)", callback_data="sb_any")],
        [
            InlineKeyboardButton(
                "🏪 Best 2 Stores (Optimized)", callback_data="sb_limit_2"
            )
        ],
        [InlineKeyboardButton("🏠 Single Store (One Stop)", callback_data="sb_single")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
    ]

    await update.message.reply_text(
        f"📋 Received {len(items)} items.\nHow do you want to organize your shopping?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SB_PREFERENCE


async def process_smart_basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mode = query.data
    await query.answer("Searching prices (Live)...")

    user_reqs = context.user_data.get("sb_list", [])

    # We fetch full cache once for the Optimizer later
    market_cache = get_all_cached_products()

    matched_items = []

    for req in user_reqs:
        best_match = None
        min_price = float("inf")

        # 1. Try to get results from Cache first (matching your search logic)
        products = get_cached_results(req.lower(), expiry_hours=24)

        # 2. If not in cache, call the actual API
        if not products:
            products = get_product_price(req, multiple=True)
            if products:
                set_cache_results(req.lower(), products)

        # 3. Find the best match among results
        if products:
            for p in products:
                # Ensure we handle different price keys
                price = float(p.get("price_eur", 0) or p.get("price", 0))
                if 0 < price < min_price:
                    min_price = price
                    best_match = p

        if best_match:
            # Ensure price is normalized for the optimizer
            best_match["price"] = min_price
            matched_items.append(best_match)

    if not matched_items:
        await query.message.edit_text(
            "No matches found for your list.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]]
            ),
        )
        return ConversationHandler.END

    # Initialize Optimizer with matched items and full market data
    opt = ShoppingOptimizer(matched_items, market_cache)
    report = ["💎 *Smart Basket Result*\n"]

    if mode == "sb_any":
        plan = opt.get_smart_split_plan()
        report.append("🌍 _Strategy: Best prices across all stores_\n")
        for store, items in plan["stores"].items():
            if items:
                report.append(f"🏪 *{store.upper()}*")
                for i in items:
                    report.append(f"• {i['name']} ({i['price']:.2f}{CURRENCY})")
                report.append("")
        report.append(f"💰 *Total: {plan['total_optimized']:.2f}{CURRENCY}*")

    elif mode == "sb_limit_2":
        plan = opt.get_limited_stores_plan(limit=2)
        report.append("🏪 _Strategy: Best 2-store combination_\n")
        for store, items in plan["stores"].items():
            if items:
                report.append(f"🏪 *{store.upper()}*")
                for i in items:
                    report.append(f"• {i['name']} ({i['price']:.2f}{CURRENCY})")
                report.append("")
        if plan.get("missing"):
            report.append("⚠️ *Not found in these 2 stores:*")
            for m in plan["missing"]:
                report.append(f"• _{m['name']}_")
        report.append(f"\n💰 *Total: {plan['total_optimized']:.2f}{CURRENCY}*")

    elif mode == "sb_single":
        plan = opt.get_single_store_plan()
        report.append(f"🏠 _Strategy: Single Store ({plan['store'].upper()})_\n")
        # Support both 'found_items' and 'items' keys depending on your optimizer version
        items_to_show = plan.get("found_items", plan.get("items", []))
        for i in items_to_show:
            report.append(f"✅ {i['name']} ({i['price']:.2f}{CURRENCY})")

        missing = plan.get("missing_items", [])
        if missing:
            report.append("\n⚠️ *Not available here:*")
            for m in missing:
                report.append(f"• _{m['name']}_")
        report.append(f"\n💰 *Total: {plan['total']:.2f}{CURRENCY}*")

    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(
        "\n".join(report),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END
