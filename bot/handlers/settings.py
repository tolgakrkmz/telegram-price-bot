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
) -> None:
    """Toggles notifications and refreshes the settings menu."""
    user_id = update.effective_user.id
    toggle_notifications(user_id)
    await settings_menu_callback(update, context)


async def select_stores_menu_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Displays the list of stores with checkboxes based on actual API data."""
    query = update.callback_query
    user_id = update.effective_user.id

    # Get current user selections
    user_stores = get_selected_stores(user_id) or ["all"]

    try:
        async with httpx.AsyncClient() as client:
            # Constructing URL with api_key as a parameter as seen in your example
            url = f"{SUPER_API_BASE}/supermarkets"
            params = {"api_key": SUPER_API_KEY}

            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()

            result = response.json()
            # The list is inside the "data" key
            raw_stores = result.get("data", [])
    except Exception as e:
        print(f"API Error fetching stores: {e}")
        raw_stores = []

    buttons = []

    # "All Stores" Button
    is_all = "all" in user_stores
    all_label = "✅ All Stores" if is_all else "🌍 All Stores"
    buttons.append([InlineKeyboardButton(all_label, callback_data="store_toggle_all")])

    # Extract store names and create buttons (2 per row)
    row = []
    for store_obj in raw_stores:
        store_name = store_obj.get("name")
        if not store_name:
            continue

        # Check if this specific store is selected
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
    data = query.data  # "store_toggle_Lidl" or "store_toggle_all"

    current_stores = get_selected_stores(user_id)
    target = data.replace("store_toggle_", "")

    if target == "all":
        new_stores = ["all"]
    else:
        # If "all" was active, remove it and start fresh with the selected store
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
