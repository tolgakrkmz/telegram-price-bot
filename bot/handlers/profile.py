from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from db.repositories.favorites_repo import get_user_favorites
from db.repositories.shopping_repo import get_user_shopping_list
from db.repositories.user_repo import (
    FREE_USER_DAILY_LIMIT,
    get_user_subscription_status,
    get_selected_stores,
    get_notification_state,
)


async def view_profile_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Displays the user profile with current stats and settings."""
    query = update.callback_query
    user = update.effective_user
    user_id = user.id

    # Fetch the full status to trigger reset logic and get fresh daily counts
    user_status = get_user_subscription_status(user_id)

    # Fetch current settings to display them
    selected_stores = get_selected_stores(user_id)
    notifications_on = get_notification_state(user_id)

    if not user_status:
        is_premium = False
        daily_requests = 0
    else:
        is_premium = user_status.get("is_premium", False)
        daily_requests = user_status.get("daily_request_count", 0)

    display_name = (
        user.first_name
        if user.first_name
        else (user.username if user.username else "Shopper")
    )

    favs = get_user_favorites(user_id) or []
    cart = get_user_shopping_list(user_id) or []

    # Format store display text
    if "all" in selected_stores or not selected_stores:
        stores_display = "All Stores 🌍"
    else:
        stores_display = ", ".join(selected_stores)

    notif_display = "✅ Enabled" if notifications_on else "❌ Disabled"

    # Common Settings Section for the message
    settings_summary = (
        f"⚙️ **Your Preferences:**\n"
        f"📍 Stores: {stores_display}\n"
        f"🔔 Alerts: {notif_display}\n\n"
    )

    if is_premium:
        badge = "💎 **PREMIUM USER**"
        status_text = (
            f"{badge}\n\n"
            f"{settings_summary}"
            f"✅ **Unlimited** Searches\n"
            f"✅ **Price Drop Alerts** Active\n\n"
            f"📊 **Today's Stats:**\n"
            f"⭐ Favorites: {len(favs)}\n"
            f"🛒 Cart items: {len(cart)}\n"
            f"👀 Searches: {daily_requests} (Unlimited)"
        )
        buttons = [
            [InlineKeyboardButton("⚙️ Edit Settings", callback_data="open_settings")],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")],
        ]
    else:
        badge = "👤 **FREE USER**"
        status_text = (
            f"{badge}\n\n"
            f"{settings_summary}"
            f"⚠️ **Daily Limits:**\n"
            f"👀 Searches: {daily_requests}/{FREE_USER_DAILY_LIMIT}\n"
            f"⭐ Favorites: {len(favs)}/3\n"
            f"🛒 Cart items: {len(cart)}/5\n\n"
            f"✨ **Upgrade for 2.50€ to get:**\n"
            f"🚀 **Unlimited Searches & Price Alerts**"
        )
        buttons = [
            [InlineKeyboardButton("⚙️ Edit Settings", callback_data="open_settings")],
            [
                InlineKeyboardButton(
                    "💎 Upgrade to Premium", callback_data="premium_info"
                )
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")],
        ]

    await query.message.edit_text(
        f"👤 **Hello, {display_name}!**\n\n{status_text}",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
