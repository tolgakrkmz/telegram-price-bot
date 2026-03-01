import requests
from telegram import Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from config.settings import ADMIN_ID, SUPER_API_BASE, SUPER_API_KEY
from db.repositories.history_repo import add_price_entry
from utils.helpers import calculate_unit_price, get_product_id
from utils.message_cache import add_message

CATEGORIES_URL = f"{SUPER_API_BASE}/categories"


async def run_bulk_logic(context: ContextTypes.DEFAULT_TYPE):
    """Internal logic to fetch categories and update database."""
    headers = {"Authorization": f"Bearer {SUPER_API_KEY}"}

    try:
        response = requests.get(CATEGORIES_URL, headers=headers)
        response.raise_for_status()
        categories_data = response.json().get("data", [])

        total_added = 0
        for category in categories_data:
            category_name = category.get("name")
            if not category_name:
                continue

            products = get_product_price(category_name, multiple=True)
            if not products:
                continue

            for p in products:
                price_val = p.get("price_eur") or p.get("price")
                unit_val = p.get("quantity") or p.get("unit")
                u_price, u_unit = calculate_unit_price(price_val, unit_val)

                store_info = p.get("supermarket")
                curr_store = (
                    store_info.get("name")
                    if isinstance(store_info, dict)
                    else p.get("store", "Unknown")
                )

                add_price_entry(
                    product_id=get_product_id(p),
                    name=p.get("name", "N/A"),
                    store=curr_store,
                    price=float(price_val) if price_val else 0.0,
                    unit_price=u_price,
                    base_unit=u_unit,
                )
                total_added += 1
        return len(categories_data), total_added
    except Exception as e:
        print(f"Bulk Logic Error: {e}")
        return 0, 0


async def bulk_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual command handler for /bulk_products."""
    user_id = update.effective_user.id
    if str(user_id) != str(ADMIN_ID):
        await update.message.reply_text("⛔ Access denied.")
        return

    status_msg = await update.message.reply_text("🔄 Starting manual bulk update...")
    cats, items = await run_bulk_logic(context)

    await status_msg.edit_text(
        f"✅ *Manual Bulk Complete!*\nCategories: {cats}\nItems: {items}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def bulk_job_wrapper(context: ContextTypes.DEFAULT_TYPE):
    """Wrapper function for the Scheduler (Job Queue)."""
    # Notify admin that auto-update started
    msg_start = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text="🤖 *Scheduled Task:* Starting automatic bulk update (Mon/Wed)...",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    add_message(ADMIN_ID, msg_start.message_id)

    cats, items = await run_bulk_logic(context)

    # Notify admin that it finished
    msg_end = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"✅ *Auto Bulk Finished*\nProcessed {cats} categories and {items} products.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    add_message(ADMIN_ID, msg_end.message_id)
