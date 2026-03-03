import datetime

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from db.repositories.smart_basket_repo import (
    delete_user_basket,
    get_baskets_by_time,
    get_user_basket,
    update_last_prices,
    update_smart_basket,
)
from db.repositories.user_repo import get_user_subscription_status, is_user_premium
from utils.helpers import calculate_unit_price, get_product_id
from utils.message_cache import add_message

# Configuration
SB_LIMIT = 20
SB_TIME, SB_INPUT, SB_REVIEW, SB_CHANGE_SEARCH, SB_SELECT_REPLACEMENT = range(5)


async def smart_basket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    # 1. Premium Check
    if not is_user_premium(user_id):
        alert_text = (
            "🚀 Smart Basket is a Premium Feature!\n\n"
            "• Daily automated price monitoring\n"
            "• Track up to 20 products\n"
            "• Instant price-drop notifications\n\n"
            "Upgrade to Premium to unlock this feature!"
        )
        await query.answer(alert_text, show_alert=True)
        return ConversationHandler.END

    # 2. Notifications Status Check
    u_status = get_user_subscription_status(user_id)
    notifications_enabled = (
        u_status.get("notifications_enabled", True) if u_status else True
    )

    if not notifications_enabled:
        text = (
            "⚠️ *Notifications are Disabled!*\n\n"
            "Your Smart Basket is active, but you won't receive any price-drop alerts "
            "because your notifications are turned off in Settings.\n\n"
            "Would you like to enable them now?"
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔔 Enable Notifications", callback_data="toggle_notifs_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    "➡️ Continue Anyway", callback_data="sb_continue_disabled"
                )
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
        msg = await query.message.edit_text(
            text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        add_message(user_id, msg.message_id)
        return SB_REVIEW

    return await sb_continue_flow(update, context)


async def sb_continue_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point after notification check or if notifications are already enabled."""
    query = update.callback_query
    user_id = update.effective_user.id

    if query:
        await query.answer()

    response = get_user_basket(user_id)

    if response and response.data:
        basket = response.data
        items = basket.get("items", [])
        alert_time = basket.get("alert_time", "Not set")

        if items:
            context.user_data.update(
                {"sb_matched_items": items, "sb_alert_time": alert_time}
            )

            total_price = sum(float(item.get("price", 0)) for item in items)

            text = f"🧺 *Your Current Smart Basket*\n\n"
            text += f"⏰ *Alert Time:* {alert_time}\n"
            text += f"📊 *Total Value:* {total_price:.2f}€\n\n"
            text += "📦 *Tracked Items:*\n"

            for idx, item in enumerate(items):
                text += f"{idx + 1}. {item['name']} ({item['price']}€)\n"

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📝 Edit Items / Time", callback_data="sb_edit_existing"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🆕 Create New Basket", callback_data="sb_new_start"
                    )
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ]

            # Use query message if coming from a callback
            msg_obj = query.message if query else update.message
            msg = await msg_obj.edit_text(
                text,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            add_message(user_id, msg.message_id)
            return SB_REVIEW

    return await start_new_basket_flow(update, context)


async def start_new_basket_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.callback_query

    if (
        query
        and query.data == "sb_new_start"
        and context.user_data.get("sb_matched_items")
    ):
        text = (
            "⚠️ *Warning!*\n\n"
            "Creating a new basket will replace your current one. "
            "Are you sure you want to proceed?"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Yes", callback_data="sb_new_confirm")],
            [InlineKeyboardButton("🔙 Back", callback_data="sb_edit_existing")],
        ]
        msg = await query.message.edit_text(
            text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        add_message(user_id, msg.message_id)
        return SB_REVIEW

    context.user_data["sb_limit"] = SB_LIMIT
    keyboard = [
        [InlineKeyboardButton("🌅 Morning (09:00)", callback_data="sbtime_09:00")],
        [InlineKeyboardButton("🌆 Evening (18:00)", callback_data="sbtime_18:00")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
    ]
    text = "✨ *Smart Basket: Step 1*\n\nSelect when you want to receive notifications:"
    if update.callback_query:
        msg = await update.callback_query.message.edit_text(
            text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        add_message(user_id, msg.message_id)
    return SB_TIME


async def handle_new_basket_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.pop("sb_matched_items", None)
    context.user_data.pop("sb_alert_time", None)
    return await start_new_basket_flow(update, context)


async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    new_time = query.data.split("_")[1]
    context.user_data["sb_alert_time"] = new_time

    items = context.user_data.get("sb_matched_items")
    if items:
        initial_prices = {item["name"]: float(item["price"]) for item in items}
        update_smart_basket(user_id, items, new_time, initial_prices)
        await query.answer("🕒 Time updated!")
        return await show_basket_review(update, context)

    await query.answer()
    msg = await query.message.edit_text(
        f"✨ *Smart Basket: Step 2*\n\nSend your list (up to {SB_LIMIT} items).\nFormat: _eggs, milk, bread_",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    add_message(user_id, msg.message_id)
    return SB_INPUT


async def handle_sb_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message:
        add_message(user_id, update.message.message_id)

    raw_items = [
        i.strip()
        for i in update.message.text.replace("\n", ",").split(",")
        if i.strip()
    ]
    if len(raw_items) > SB_LIMIT:
        msg = await update.message.reply_text(f"❌ Limit: {SB_LIMIT} items.")
        add_message(user_id, msg.message_id)
        return SB_INPUT

    processing = await update.message.reply_text("🔎 Matching items...")
    add_message(user_id, processing.message_id)

    matched = []
    for item in raw_items:
        res = get_product_price(item, multiple=True)
        if res:
            best = res[0]
            matched.append(
                {
                    "id": best.get("id"),
                    "name": best.get("name"),
                    "price": best.get("price"),
                    "store": best.get("store"),
                    "original_query": item,
                }
            )
        else:
            matched.append(
                {
                    "id": None,
                    "name": f"Check: {item}",
                    "price": 0.0,
                    "store": "Not found",
                    "original_query": item,
                }
            )

    context.user_data["sb_matched_items"] = matched

    alert_time = context.user_data.get("sb_alert_time")
    if alert_time:
        initial_prices = {item["name"]: float(item["price"]) for item in matched}
        update_smart_basket(user_id, matched, alert_time, initial_prices)

    await processing.delete()
    return await show_basket_review(update, context)


async def show_basket_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = context.user_data.get("sb_matched_items", [])
    alert_time = context.user_data.get("sb_alert_time", "Not set")

    total_price = sum(float(item.get("price", 0)) for item in items)

    text = "🧺 *Your Active Smart Basket*\n\n"
    text += f"⏰ *Time:* {alert_time}\n"
    text += f"📊 *Total Value:* {total_price:.2f}€\n\n"
    text += "📦 *Items:*\n"

    keyboard = []
    for idx, item in enumerate(items):
        text += (
            f"\n*{idx + 1}. {item['name']}*\n💰 {item['price']}€ @ {item['store']}\n"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔄 Change Item {idx + 1}", callback_data=f"sb_change_{idx}"
                )
            ]
        )

    keyboard.extend(
        [
            [
                InlineKeyboardButton(
                    "🕒 Change Alert Time", callback_data="sb_edit_time_only"
                )
            ],
            [InlineKeyboardButton("🗑️ Clear Basket", callback_data="sb_clear_confirm")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]
    )

    markup = InlineKeyboardMarkup(keyboard)
    msg_obj = update.callback_query.message if update.callback_query else update.message

    try:
        final_msg = await msg_obj.edit_text(
            text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=markup
        )
    except:
        final_msg = await msg_obj.reply_text(
            text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=markup
        )

    add_message(user_id, final_msg.message_id)
    return SB_REVIEW


async def handle_time_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.answer()
    keyboard = [
        [
            InlineKeyboardButton("🌅 09:00", callback_data="sbtime_09:00"),
            InlineKeyboardButton("🌆 18:00", callback_data="sbtime_18:00"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="sb_edit_existing")],
    ]
    msg = await update.callback_query.message.edit_text(
        "🕒 *Select notification time:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    add_message(user_id, msg.message_id)
    return SB_TIME


async def handle_change_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.answer()
    context.user_data["editing_idx"] = int(update.callback_query.data.split("_")[2])
    msg = await update.callback_query.message.edit_text("🔎 Send new product name:")
    add_message(user_id, msg.message_id)
    return SB_CHANGE_SEARCH


async def process_replacement_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    search_query = update.message.text.strip().lower()

    if update.message:
        add_message(user_id, update.message.message_id)

    products = get_product_price(search_query, multiple=True)
    is_from_cache = False
    cache_date = "recently"

    if not products:
        from db.repositories.cache_repo import CACHE_TABLE
        from db.supabase_client import supabase

        response = (
            supabase.table(CACHE_TABLE).select("*").eq("query", search_query).execute()
        )

        if response.data:
            cache_row = response.data[0]
            products = cache_row.get("results", [])
            is_from_cache = True

            try:
                raw_date = cache_row.get("created_at")
                if raw_date:
                    dt = datetime.datetime.fromisoformat(
                        raw_date.replace("Z", "+00:00")
                    )
                    cache_date = dt.strftime("%d.%m.%Y")
            except:
                if products and "brochure" in products[0]:
                    cache_date = products[0]["brochure"].get(
                        "valid_from", "unknown date"
                    )

    if not products:
        msg = await update.message.reply_text(
            "❌ No results found (API limit). Try again later:"
        )
        add_message(user_id, msg.message_id)
        return SB_CHANGE_SEARCH

    for p in products:
        p["calc_unit_price"], p["base_unit"] = calculate_unit_price(
            p.get("price_eur") or p.get("price"), p.get("quantity") or p.get("unit")
        )

    products.sort(key=lambda x: x["calc_unit_price"] or float("inf"))

    msg = await update.message.reply_text(
        "🎯 *Select replacement:*", parse_mode=constants.ParseMode.MARKDOWN
    )
    add_message(user_id, msg.message_id)

    temp_res, msgs = {}, []
    for p in products[:5]:
        p_id = get_product_id(p)
        temp_res[p_id] = p

        price_val = float(p.get("price_eur") or p.get("price") or 0)

        prefix = (
            f"⚠️ *Showing last known price* (from {cache_date}):\n"
            if is_from_cache
            else ""
        )
        cap = (
            f"{prefix}"
            f"🛒 *{p.get('name')}*\n💰 **{price_val:.2f}€**\n🏬 {p.get('store')}\n"
        )

        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Select", callback_data=f"sb_rep_{p_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data="sb_back")],
            ]
        )

        try:
            m = (
                await update.message.reply_photo(
                    p.get("image_url"),
                    caption=cap,
                    reply_markup=kb,
                    parse_mode=constants.ParseMode.MARKDOWN,
                )
                if p.get("image_url")
                else await update.message.reply_text(
                    cap, reply_markup=kb, parse_mode=constants.ParseMode.MARKDOWN
                )
            )
            msgs.append(m.message_id)
            add_message(user_id, m.message_id)
        except Exception as e:
            print(f"Error: {e}")

    context.user_data.update(
        {"temp_search_results": temp_res, "messages_to_clear": msgs}
    )
    return SB_SELECT_REPLACEMENT


async def finalize_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    p_id = query.data.replace("sb_rep_", "")
    res = context.user_data.get("temp_search_results", {}).get(p_id)

    for m_id in context.user_data.get("messages_to_clear", []):
        try:
            await context.bot.delete_message(user_id, m_id)
        except:
            pass

    idx = context.user_data["editing_idx"]
    items = context.user_data["sb_matched_items"]
    items[idx].update(
        {
            "id": p_id,
            "name": res.get("name"),
            "price": float(res.get("price_eur") or res.get("price")),
            "store": res.get("store"),
        }
    )

    alert_time = context.user_data.get("sb_alert_time")
    if alert_time:
        initial_prices = {item["name"]: float(item["price"]) for item in items}
        update_smart_basket(user_id, items, alert_time, initial_prices)
        await query.answer("✅ Item replaced and saved!")

    return await show_basket_review(update, context)


async def smart_basket_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now(pytz.timezone("Europe/Sofia")).strftime("%H:%M")
    baskets = get_baskets_by_time(now)
    if not baskets or not baskets.data:
        return

    for b in baskets.data:
        u_id = b["user_id"]
        u_status = get_user_subscription_status(u_id)
        if not u_status or not u_status.get("notifications_enabled", True):
            continue

        history_prices = b.get("last_prices") or {}
        new_prices, alerts = {}, []
        for item in b["items"]:
            res = get_product_price(item["name"], multiple=True)
            if res:
                match = res[0]
                curr_p = float(match.get("price"))
                new_prices[item["name"]] = curr_p
                old_p = history_prices.get(item["name"])
                if old_p and curr_p < float(old_p):
                    alerts.append(
                        f"📉 *{item['name']}*: *{curr_p}€* (was {old_p}€) @ {match['store']}"
                    )

        update_last_prices(u_id, new_prices)
        if alerts:
            await context.bot.send_message(
                u_id,
                "🎁 *Smart Basket Price Drop!*\n\n" + "\n".join(alerts),
                parse_mode="Markdown",
            )


async def confirm_clear_basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kb = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="sb_clear_final")],
        [InlineKeyboardButton("🔙 No", callback_data="sb_edit_existing")],
    ]
    msg = await update.callback_query.message.edit_text(
        "🗑️ *Delete your Smart Basket?*\nThis cannot be undone.",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    add_message(user_id, msg.message_id)
    return SB_REVIEW


async def execute_clear_basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    delete_user_basket(user_id)
    context.user_data.pop("sb_matched_items", None)
    context.user_data.pop("sb_alert_time", None)
    msg = await update.callback_query.message.edit_text(
        "🗑️ *Basket cleared!*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]]
        ),
    )
    add_message(user_id, msg.message_id)
    return ConversationHandler.END
