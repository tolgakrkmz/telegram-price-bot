import asyncio
import datetime

from telegram import CallbackQuery, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.repositories.favorites_repo import get_user_favorites

# Updated import: changed add_price_history_record to add_price_entry
from db.repositories.history_repo import add_price_entry, get_product_history
from db.repositories.user_repo import (
    is_user_premium,
    toggle_notifications,
)
from db.supabase_client import supabase
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

CURRENCY = "€"

# ==============================
# CALLBACK HANDLERS
# ==============================


async def handle_toggle_alerts(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Toggles price alerts for premium users and handles redirection."""
    query: CallbackQuery = update.callback_query
    user_id = query.from_user.id

    premium_status = is_user_premium(user_id)

    if premium_status is not True:
        limit_text = (
            "🔔 Premium Feature!\n\n"
            "Enable automatic Price Drop alerts for only 2.50 EUR/month! 📉\n\n"
            "Stay ahead of price changes!"
        )
        await query.answer(limit_text, show_alert=True)
        return

    # Toggle status in DB
    new_status = toggle_notifications(user_id)
    status_text = "enabled ✅" if new_status else "disabled ❌"
    await query.answer(f"Notifications {status_text}!")

    # REDIRECTION LOGIC:
    # If the user enabled notifications from the Smart Basket warning,
    # send them back to the basket flow.
    from handlers.smart_basket import sb_continue_flow

    # We can check if we were in a Smart Basket context or just use the flow
    # If notifications were just ENABLED, it's a good UX to go back to SB
    if new_status:
        return await sb_continue_flow(update, context)

    # Default behavior: update main menu
    try:
        await query.edit_message_reply_markup(reply_markup=main_menu_keyboard(user_id))
    except Exception as e:
        print(f"Error updating keyboard: {e}")


# ==============================
# SCHEDULED TASKS
# ==============================


async def global_price_update(context: ContextTypes.DEFAULT_TYPE):
    """Updates prices and sends alerts only to Premium users with notifications enabled."""
    try:
        response = (
            supabase.table("favorites")
            .select("*, users!inner(notifications_enabled, is_premium)")
            .eq("users.notifications_enabled", True)
            .eq("users.is_premium", True)
            .execute()
        )
        favorites = response.data
    except Exception as e:
        print(f"Error fetching favorites for update: {e}")
        return

    if not favorites:
        return

    for fav in favorites:
        product_id = fav.get("product_id")
        user_id = fav.get("user_id")

        old_price = float(fav.get("price_eur") or fav.get("price") or 0)
        fresh_data = get_product_price(fav.get("name"))  # Use name for search

        if not fresh_data:
            continue

        # Handle potential multiple results from API
        if isinstance(fresh_data, list):
            fresh_data = fresh_data[0]

        new_price = float(fresh_data.get("price_eur") or fresh_data.get("price") or 0)

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
                supabase.table("favorites").update({"price_eur": new_price}).eq(
                    "id", fav.get("id")
                ).execute()
            except Exception as e:
                print(f"Failed to send alert to {user_id}: {e}")


async def check_expiring_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends expiring deal alerts only to Premium users."""
    today = datetime.datetime.now().date().isoformat()
    try:
        response = (
            supabase.table("favorites")
            .select(
                "user_id, name, price_eur, store, users!inner(notifications_enabled, is_premium)"
            )
            .eq("valid_until", today)
            .eq("users.notifications_enabled", True)
            .eq("users.is_premium", True)
            .execute()
        )
        if not response.data:
            return
        for item in response.data:
            user_id = item.get("user_id")
            msg = (
                f"⚠️ *Last Chance!*\n"
                f"The promotion for *{item['name']}* ends **today**!\n"
                f"💰 Price: {item['price_eur']:.2f}€\n"
                f"🏬 Store: {item.get('store', 'N/A')}"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to send expiring alert to {user_id}: {e}")
    except Exception as e:
        print(f"Supabase Expiring Alerts Error: {e}")


async def check_expiring_tomorrow_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends tomorrow's expiring deal alerts only to Premium users."""
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).date().isoformat()
    try:
        response = (
            supabase.table("favorites")
            .select(
                "user_id, name, store, users!inner(notifications_enabled, is_premium)"
            )
            .eq("valid_until", tomorrow)
            .eq("users.notifications_enabled", True)
            .eq("users.is_premium", True)
            .execute()
        )
        if not response.data:
            return
        for item in response.data:
            user_id = item.get("user_id")
            msg = (
                f"🔔 *Reminder: Deal Ending Soon*\n"
                f"The promotion for *{item['name']}* expires **tomorrow**.\n"
                f"🏬 Store: {item.get('store', 'N/A')}"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id, text=msg, parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Failed to send tomorrow alert to {user_id}: {e}")
    except Exception as e:
        print(f"Supabase Tomorrow Alerts Error: {e}")


# ==============================
# MANUAL COMMANDS
# ==============================


async def update_favorites_prices(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manual sync with new history logging support."""
    user_id = update.effective_user.id
    fav_list = get_user_favorites(user_id) or []

    add_message(user_id, update.message.message_id)

    if not fav_list:
        msg = await update.message.reply_text("⭐ Your favorites list is empty.")
        add_message(user_id, msg.message_id)
        return

    status_msg = await update.message.reply_text("🔄 Syncing latest prices...")
    add_message(user_id, status_msg.message_id)

    report = ["📊 *Price Report:*\n"]

    for p in fav_list:
        pid = str(p.get("product_id"))
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.2)

        if not new_results:
            continue

        match = next((i for i in new_results if i.get("store") == p.get("store")), None)
        if match:
            new_p = float(match.get("price_eur") or match.get("price", 0))
            old_p = float(p.get("price_eur") or p.get("price", 0))

            # Updated function call to add_price_entry
            add_price_entry(
                product_id=pid,
                name=p["name"],
                store=p.get("store", "Unknown"),
                price=new_p,
            )

            diff = new_p - old_p
            change = f"({'-' if diff < 0 else '+'}{abs(diff):.2f})" if diff != 0 else ""
            report.append(f"✅ {p['name']}: **{new_p:.2f}{CURRENCY}** {change}")

    await status_msg.edit_text(
        "\n".join(report), parse_mode=constants.ParseMode.MARKDOWN
    )
