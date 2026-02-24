import asyncio
from collections import defaultdict

from telegram import CallbackQuery, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.repositories.favorites_repo import get_all_favorites_from_db, get_user_favorites
from db.repositories.history_repo import add_price_history_record
from db.repositories.user_repo import get_users_to_notify, toggle_notifications
from utils.menu import main_menu_keyboard

CURRENCY = "€"

# ==============================
# CALLBACK HANDLERS
# ==============================


async def handle_toggle_alerts(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles the toggle button click in the main menu."""
    query: CallbackQuery = update.callback_query
    user_id = query.from_user.id

    new_status = toggle_notifications(user_id)
    status_text = "enabled ✅" if new_status else "disabled ❌"
    await query.answer(f"Notifications {status_text}!")

    try:
        await query.edit_message_reply_markup(reply_markup=main_menu_keyboard(user_id))
    except Exception:
        pass


# ==============================
# SCHEDULED TASKS
# ==============================


from telegram import Update
from telegram.ext import ContextTypes
from db.repositories.favorites_repo import get_all_favorites_from_db
from api.supermarket import get_product_price
from db.supabase_client import supabase


async def global_price_update(context: ContextTypes.DEFAULT_TYPE):
    """
    Automatic task for the job_queue.
    Checks all favorites and sends alerts for price drops.
    """
    favorites = get_all_favorites_from_db()

    if not favorites:
        return

    for fav in favorites:
        product_id = fav.get("product_id")
        user_id = fav.get("user_id")

        # Current price in our database
        old_price = float(fav.get("price_eur") or fav.get("price") or 0)

        # Get fresh price from the store API
        fresh_data = get_product_price(product_id)
        if not fresh_data:
            continue

        new_price = float(fresh_data.get("price_eur") or fresh_data.get("price") or 0)

        # Alert if the price has dropped
        if new_price < old_price:
            diff = old_price - new_price

            message = (
                f"📉 *Price Drop Alert!*\n"
                f"🛒 *{fav.get('name')}*\n"
                f"💰 Was: {old_price:.2f}€\n"
                f"✅ Now: **{new_price:.2f}€**\n"
                f"💸 Saved: {diff:.2f}€"
            )

            try:
                await context.bot.send_message(
                    chat_id=user_id, text=message, parse_mode="Markdown"
                )

                # Update DB with the new lower price to prevent repeat alerts
                supabase.table("favorites").update({"price_eur": new_price}).eq(
                    "id", fav.get("id")
                ).execute()
            except Exception as e:
                print(f"Failed to send alert to {user_id}: {e}")


# ==============================
# MANUAL COMMANDS
# ==============================


async def update_favorites_prices(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manual update triggered by /update_prices command."""
    user_id = update.effective_user.id
    fav_list = get_user_favorites(user_id) or []

    if not fav_list:
        await update.message.reply_text("⭐ Your favorites list is empty.")
        return

    status_msg = await update.message.reply_text("🔄 Syncing latest prices...")
    report = ["📊 *Price Report:*\n"]

    for p in fav_list:
        pid = str(p.get("product_id"))
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.2)

        match = next((i for i in new_results if i.get("store") == p.get("store")), None)
        if match:
            new_p = float(match.get("price_eur") or match.get("price", 0))
            old_p = float(p.get("price_eur") or p.get("price", 0))

            add_price_history_record(pid, new_p)

            diff = new_p - old_p
            change = f"({'-' if diff < 0 else '+'}{abs(diff):.2f})" if diff != 0 else ""
            report.append(f"✅ {p['name']}: **{new_p:.2f}{CURRENCY}** {change}")

    await status_msg.edit_text(
        "\n".join(report), parse_mode=constants.ParseMode.MARKDOWN
    )


async def check_expiring_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporary placeholder for expiring alerts."""
    print(
        "DEBUG: check_expiring_alerts was called but is not yet implemented with Supabase."
    )
    pass


async def check_expiring_tomorrow_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Temporary placeholder for expiring tomorrow alerts."""
    print(
        "DEBUG: check_expiring_tomorrow_alerts was called but is not yet implemented with Supabase."
    )
    pass
