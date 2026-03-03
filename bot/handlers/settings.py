import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from config.settings import SUPER_API_BASE, SUPER_API_KEY
from db.repositories.user_repo import (
    get_notification_state,
    get_selected_stores,
    toggle_notifications,
    update_selected_stores,
)


async def settings_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Main settings menu: Notifications and Store Selection."""
    query = update.callback_query
    user_id = update.effective_user.id

    notif_on = get_notification_state(user_id)
    # The emoji will now update dynamically
    notif_label = "🔔 Notifications: ON" if notif_on else "🔕 Notifications: OFF"

    buttons = [
        [InlineKeyboardButton(notif_label, callback_data="toggle_notifs_settings")],
        [InlineKeyboardButton("🛒 Select Stores", callback_data="select_stores_menu")],
        [InlineKeyboardButton("⬅️ Back to Profile", callback_data="view_profile")],
    ]

    await query.message.edit_text(
        "⚙️ **Settings**\n\nManage your notifications and filter the stores you want to search in.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def toggle_notifications_settings_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Toggles notification state and redirects to Smart Basket flow IF the user is there."""
    query = update.callback_query
    user_id = update.effective_user.id

    # 1. Toggle status in DB
    new_status = toggle_notifications(user_id)

    # 2. SILENT SUCCESS MESSAGE (Toast at the top)
    status_text = "enabled ✅" if new_status else "disabled ❌"
    await query.answer(f"Notifications {status_text}!")

    # 3. DIRECT REDIRECTION LOGIC
    # Check if the user is currently in the Smart Basket flow
    # We use 'sb_alert_time' or 'sb_matched_items' as indicators
    if new_status and (
        context.user_data.get("sb_alert_time")
        or context.user_data.get("sb_matched_items")
    ):
        from handlers.smart_basket import sb_continue_flow

        # Skip settings menu and go straight to the basket
        return await sb_continue_flow(update, context)

    # 4. DEFAULT: Refresh the settings menu (if user is just browsing settings)
    return await settings_menu_callback(update, context)


async def select_stores_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Displays the list of stores with checkboxes based on actual API data."""
    query = update.callback_query
    user_id = update.effective_user.id

    user_stores = get_selected_stores(user_id) or ["all"]

    try:
        async with httpx.AsyncClient() as client:
            url = f"{SUPER_API_BASE}/supermarkets"
            params = {"api_key": SUPER_API_KEY}

            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()

            result = response.json()
            raw_stores = result.get("data", [])
    except Exception:
        raw_stores = []

    buttons = []

    # "All Stores" Button
    is_all = "all" in user_stores
    all_label = "✅ All Stores" if is_all else "🌍 All Stores"
    buttons.append([InlineKeyboardButton(all_label, callback_data="store_toggle_all")])

    # 2 per row
    row = []
    for store_obj in raw_stores:
        store_name = store_obj.get("name")
        if not store_name:
            continue

        is_selected = store_name in user_stores and not is_all
        label = f"✅ {store_name}" if is_selected else store_name

        row.append(
            InlineKeyboardButton(label, callback_data=f"store_toggle_{store_name}")
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append(
        [InlineKeyboardButton("⬅️ Back to Settings", callback_data="open_settings")]
    )

    await query.message.edit_text(
        "🛒 **Selected Stores**\n\nChoose where you want to search for products. Selecting specific stores will filter all future searches.",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def store_toggle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handles the logic of selecting/deselecting stores."""
    query = update.callback_query
    user_id = update.effective_user.id
    target = query.data.replace("store_toggle_", "")

    current_stores = get_selected_stores(user_id)

    if target == "all":
        new_stores = ["all"]
    else:
        if "all" in current_stores:
            new_stores = [target]
        elif target in current_stores:
            current_stores.remove(target)
            new_stores = current_stores if current_stores else ["all"]
        else:
            current_stores.append(target)
            new_stores = current_stores

    update_selected_stores(user_id, new_stores)
    await select_stores_menu_callback(update, context)
