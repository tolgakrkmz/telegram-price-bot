import asyncio
from collections import defaultdict

from telegram import CallbackQuery, Update, constants
from telegram.ext import ContextTypes

from api.supermarket import get_product_price
from db.storage import (
    get_all_favorites,
    get_expiring_products,
    get_expiring_products_tomorrow,
    get_favorites,
    get_users_to_notify,
    toggle_notifications,
    update_price_history,
)
from utils.menu import main_menu_keyboard

CURRENCY = "€"

# ==============================
# CALLBACK HANDLERS
# ==============================

async def handle_toggle_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the toggle button click in the main menu."""
    query: CallbackQuery = update.callback_query
    user_id = query.from_user.id
    
    new_status = toggle_notifications(user_id)
    status_text = "enabled" if new_status else "disabled"
    await query.answer(f"Notifications {status_text}!")
    
    await query.edit_message_reply_markup(
        reply_markup=main_menu_keyboard(user_id)
    )

# ==============================
# SCHEDULED TASKS
# ==============================

async def check_expiring_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notifies users about promotions ending today."""
    user_ids = get_users_to_notify()
    
    for uid in user_ids:
        expiring_items = get_expiring_products(uid)
        if not expiring_items:
            continue
            
        message = "⚠️ *Promotions Expiring Today!*\n\n"
        for item in expiring_items:
            price = float(item.get("price", 0))
            message += f"• {item['name']} - **{price:.2f}{CURRENCY}**\n"
            message += f"  🏬 {item['store']}\n\n"
        
        message += "🕒 Last chance to get these deals!"
        
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=message,
                parse_mode=constants.ParseMode.MARKDOWN
            )
            await asyncio.sleep(0.05)
        except Exception:
            continue

async def check_expiring_tomorrow_alerts(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notifies users about promotions ending tomorrow with a separate menu at the end."""
    user_ids = get_users_to_notify()
    
    for uid in user_ids:
        items = get_expiring_products_tomorrow(uid)
        if not items:
            continue
            
        await context.bot.send_message(
            chat_id=uid, 
            text="⏳ *Reminder: These promos end TOMORROW!*",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        for item in items:
            name = item.get("name", "N/A")
            price = float(item.get("price_eur") or item.get("price", 0))
            unit = item.get("quantity") or item.get("unit", "")
            store = item.get("store", "Unknown")
            image = item.get("image_url") or item.get("image")
            discount = item.get("discount")
            u_price = item.get("calc_unit_price")
            u_unit = item.get("base_unit", "kg")
            
            unit_info = f"⚖️ Unit Price: **{u_price:.2f}{CURRENCY}/{u_unit}**\n" if u_price else ""

            caption = (
                f"🛒 *{name}*\n"
                f"💰 Price: **{price:.2f}{CURRENCY}** ({unit})\n"
                f"{unit_info}"
                f"🏬 Store: {store}\n"
            )
            if discount:
                caption += f"💸 Discount: {discount}%\n"

            try:
                if image:
                    await context.bot.send_photo(
                        chat_id=uid,
                        photo=image,
                        caption=caption,
                        parse_mode=constants.ParseMode.MARKDOWN
                    )
                else:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=caption,
                        parse_mode=constants.ParseMode.MARKDOWN
                    )
                await asyncio.sleep(0.2)
            except Exception:
                continue

        await context.bot.send_message(
            chat_id=uid,
            text="🏠 *Main Menu*",
            reply_markup=main_menu_keyboard(uid),
            parse_mode=constants.ParseMode.MARKDOWN
        )

async def global_price_update(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Updates unique favorite products and sends price drop/increase alerts with photos."""
    all_data = get_all_favorites()
    if not all_data:
        return

    unique_prods: dict[str, dict] = {}
    product_watchers = defaultdict(list)

    for user_id, user_data in all_data.items():
        if not user_data.get("notifications_enabled"):
            continue
            
        for pid, p in user_data.items():
            if isinstance(p, dict) and pid not in ["shopping_list", "notifications_enabled"]:
                unique_prods[pid] = p
                product_watchers[pid].append(user_id)

    for pid, p in unique_prods.items():
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.5)

        if not isinstance(new_results, list):
            continue

        match = next((i for i in new_results if i["store"] == p["store"]), None)
        
        if match:
            new_price = float(match.get("price_eur") or match.get("price", 0))
            old_price = float(p.get("price_eur") or p.get("price", 0))

            if new_price != old_price:
                update_price_history(pid, new_price, p["name"], p["store"])
                
                diff = abs(old_price - new_price)
                is_drop = new_price < old_price
                icon = "📉" if is_drop else "📈"
                alert_type = "Price Drop Alert!" if is_drop else "Price Alert!"
                
                caption = (
                    f"{icon} *{alert_type}*\n\n"
                    f"🛒 *{p['name']}*\n"
                    f"💰 New Price: **{new_price:.2f}{CURRENCY}**\n"
                    f"📉 Change: **{'-' if is_drop else '+'}{diff:.2f}{CURRENCY}**\n"
                    f"🏬 Store: {p['store']}"
                )

                for user_id in product_watchers[pid]:
                    try:
                        image = p.get("image_url") or p.get("image")
                        if image:
                            await context.bot.send_photo(
                                chat_id=user_id,
                                photo=image,
                                caption=caption,
                                parse_mode=constants.ParseMode.MARKDOWN
                            )
                        else:
                            await context.bot.send_message(
                                chat_id=user_id,
                                text=caption,
                                parse_mode=constants.ParseMode.MARKDOWN
                            )
                        
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="🏠 *Main Menu*",
                            reply_markup=main_menu_keyboard(user_id),
                            parse_mode=constants.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        print(f"Error notifying user {user_id}: {e}")
                        continue

# ==============================
# MANUAL COMMANDS
# ==============================

async def update_favorites_prices(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual update triggered by /update_prices command."""
    user_id = update.effective_user.id
    favorites = get_favorites(user_id)
    if not favorites:
        await update.message.reply_text("⭐ Your favorites list is empty.")
        return

    status_msg = await update.message.reply_text("🔄 Syncing latest prices...")
    report = ["📊 *Price Report:*\n"]

    for pid, p in favorites.items():
        new_results = get_product_price(p["name"], multiple=True)
        await asyncio.sleep(1.2)
        match = next((i for i in new_results if i["store"] == p["store"]), None)
        if match:
            new_p = float(match["price"])
            old_p = float(p.get("price", 0))
            update_price_history(pid, new_p, p["name"], p["store"])
            diff = new_p - old_p
            change = f"({'-' if diff < 0 else '+'}{abs(diff):.2f})" if diff != 0 else ""
            report.append(f"✅ {p['name']}: **{new_p:.2f}{CURRENCY}** {change}")

    await status_msg.edit_text("\n".join(report), parse_mode=constants.ParseMode.MARKDOWN)