import datetime
import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes, ConversationHandler

from api.supermarket import get_product_price
from db.repositories.smart_basket_repo import (
    get_baskets_by_time,
    get_user_basket,
    update_last_prices,
    update_smart_basket,
    delete_user_basket,
)
from db.repositories.user_repo import get_user_subscription_status, is_user_premium
from utils.helpers import calculate_unit_price, get_product_id

# Configuration
SB_LIMIT = 20
SB_TIME, SB_INPUT, SB_REVIEW, SB_CHANGE_SEARCH, SB_SELECT_REPLACEMENT = range(5)


async def smart_basket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

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
            text = f"🧺 *Your Current Smart Basket*\n\n⏰ *Alert Time:* {alert_time}\n📦 *Items:*\n"
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
            await query.message.edit_text(
                text,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return SB_REVIEW

    return await start_new_basket_flow(update, context)


async def start_new_basket_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sb_limit"] = SB_LIMIT
    keyboard = [
        [InlineKeyboardButton("🌅 Morning (09:00)", callback_data="sbtime_09:00")],
        [InlineKeyboardButton("🌆 Evening (18:00)", callback_data="sbtime_18:00")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
    ]
    text = "✨ *Smart Basket: Step 1*\n\nSelect when you want to receive notifications:"
    if update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    return SB_TIME


async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["sb_alert_time"] = query.data.split("_")[1]

    if context.user_data.get("sb_matched_items"):
        return await show_basket_review(update, context)

    await query.message.edit_text(
        f"✨ *Smart Basket: Step 2*\n\nSend your list (up to {SB_LIMIT} items).\nFormat: _eggs, milk, bread_",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SB_INPUT


async def handle_sb_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_items = [
        i.strip()
        for i in update.message.text.replace("\n", ",").split(",")
        if i.strip()
    ]
    if len(raw_items) > SB_LIMIT:
        await update.message.reply_text(f"❌ Limit: {SB_LIMIT} items.")
        return SB_INPUT

    processing = await update.message.reply_text("🔎 Matching items...")
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
    await processing.delete()
    return await show_basket_review(update, context)


async def show_basket_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items, alert_time = (
        context.user_data.get("sb_matched_items", []),
        context.user_data.get("sb_alert_time"),
    )
    existing = get_user_basket(update.effective_user.id)
    btn_text = (
        "💾 Save Changes" if (existing and existing.data) else "✅ Save & Activate"
    )

    text = f"📋 *Smart Basket Review*\n\n⏰ *Time:* {alert_time}\n📦 *Items:*\n\n"
    keyboard = []
    for idx, item in enumerate(items):
        text += (
            f"*{idx + 1}. {item['name']}*\n💰 {item['price']}€ @ {item['store']}\n\n"
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
            [InlineKeyboardButton(btn_text, callback_data="sb_finalize")],
            [InlineKeyboardButton("🗑️ Clear Basket", callback_data="sb_clear_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")],
        ]
    )

    markup = InlineKeyboardMarkup(keyboard)
    msg = update.callback_query.message if update.callback_query else update.message
    try:
        await msg.edit_text(
            text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=markup
        )
    except:
        await msg.reply_text(
            text, parse_mode=constants.ParseMode.MARKDOWN, reply_markup=markup
        )
    return SB_REVIEW


async def handle_time_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [
            InlineKeyboardButton("🌅 09:00", callback_data="sbtime_09:00"),
            InlineKeyboardButton("🌆 18:00", callback_data="sbtime_18:00"),
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="sb_edit_existing")],
    ]
    await update.callback_query.message.edit_text(
        "🕒 *Select notification time:*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SB_TIME


async def handle_change_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["editing_idx"] = int(update.callback_query.data.split("_")[2])
    await update.callback_query.message.edit_text("🔎 Send new product name:")
    return SB_CHANGE_SEARCH


async def process_replacement_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    products = get_product_price(update.message.text.strip().lower(), multiple=True)
    if not products:
        await update.message.reply_text("❌ No results. Try again:")
        return SB_CHANGE_SEARCH

    for p in products:
        p["calc_unit_price"], p["base_unit"] = calculate_unit_price(
            p.get("price_eur") or p.get("price"), p.get("quantity") or p.get("unit")
        )

    products.sort(key=lambda x: x["calc_unit_price"] or float("inf"))
    await update.message.reply_text(
        "🎯 *Select replacement:*", parse_mode=constants.ParseMode.MARKDOWN
    )

    temp_res, msgs = {}, []
    for p in products[:5]:
        p_id = get_product_id(p)
        temp_res[p_id] = p
        cap = (
            f"🛒 *{p.get('name')}*\n💰 **{p.get('price'):.2f}€**\n🏬 {p.get('store')}\n"
        )
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Select", callback_data=f"sb_rep_{p_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data="sb_back")],
            ]
        )
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

    context.user_data.update(
        {"temp_search_results": temp_res, "messages_to_clear": msgs}
    )
    return SB_SELECT_REPLACEMENT


async def finalize_replacement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p_id = update.callback_query.data.replace("sb_rep_", "")
    res = context.user_data.get("temp_search_results", {}).get(p_id)
    for m_id in context.user_data.get("messages_to_clear", []):
        try:
            await context.bot.delete_message(update.effective_user.id, m_id)
        except:
            pass

    idx = context.user_data["editing_idx"]
    context.user_data["sb_matched_items"][idx].update(
        {
            "id": p_id,
            "name": res.get("name"),
            "price": float(res.get("price_eur") or res.get("price")),
            "store": res.get("store"),
        }
    )
    return await show_basket_review(update, context)


async def finalize_sb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items, alert_time = (
        context.user_data.get("sb_matched_items"),
        context.user_data.get("sb_alert_time"),
    )
    if not items or not alert_time:
        return ConversationHandler.END

    update_smart_basket(user_id, items, alert_time)
    u_status = get_user_subscription_status(user_id)
    warn = (
        "\n\n⚠️ *Notifications are OFF!*"
        if u_status and not u_status.get("notifications_enabled")
        else ""
    )
    kb = [[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]]
    if warn:
        kb.insert(0, [InlineKeyboardButton("🔔 Enable", callback_data="toggle_alerts")])

    await update.callback_query.message.edit_text(
        f"🚀 *Smart Basket Saved!*{warn}",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return ConversationHandler.END


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

        new_prices, alerts = {}, []
        for item in b["items"]:
            res = get_product_price(item["name"], multiple=True)
            if res:
                match = res[0]
                curr_p = float(match.get("price"))
                new_prices[item["name"]] = curr_p
                if b.get("last_prices", {}).get(item["name"]) and curr_p < float(
                    b["last_prices"][item["name"]]
                ):
                    alerts.append(
                        f"📉 *{item['name']}*: *{curr_p}€* @ {match['store']}"
                    )

        update_last_prices(u_id, new_prices)
        if alerts:
            await context.bot.send_message(
                u_id,
                "🎁 *Smart Basket Price Drop!*\n\n" + "\n".join(alerts),
                parse_mode="Markdown",
            )


async def confirm_clear_basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("✅ Yes, Delete", callback_data="sb_clear_final")],
        [InlineKeyboardButton("🔙 No", callback_data="sb_edit_existing")],
    ]
    await update.callback_query.message.edit_text(
        "🗑️ *Delete your Smart Basket?*\nThis cannot be undone.",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return SB_REVIEW


async def execute_clear_basket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_user_basket(update.effective_user.id)
    context.user_data.pop("sb_matched_items", None)
    context.user_data.pop("sb_alert_time", None)
    await update.callback_query.message.edit_text(
        "🗑️ *Basket cleared!*",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 Menu", callback_data="main_menu")]]
        ),
    )
    return ConversationHandler.END
