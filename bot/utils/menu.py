from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from db.repositories.user_repo import get_notification_state


def main_menu_keyboard(user_id: int):
    """Main navigation menu with dynamic notification toggle."""

    # Check current notification status from storage
    notifications_on = get_notification_state(user_id)
    notif_icon = "🔔" if notifications_on else "🔕"
    notif_text = f"{notif_icon} Notifications: {'ON' if notifications_on else 'OFF'}"

    keyboard = [
        [InlineKeyboardButton("🔍 Search Products", callback_data="search")],
        [
            InlineKeyboardButton("⭐ Favorites", callback_data="list_favorites"),
            InlineKeyboardButton("🛒 Cart", callback_data="shopping_list"),
        ],
        [InlineKeyboardButton(notif_text, callback_data="toggle_notifications")],
        [InlineKeyboardButton("👤 My Profile", callback_data="view_profile")],
        [
            InlineKeyboardButton("ℹ️ Info & Help", callback_data="bot_info"),
            InlineKeyboardButton("🧹 Clear Chat", callback_data="clear_chat"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def favorites_keyboard(favorites: dict):
    """
    Generates a keyboard for favorites with history, cart, and delete options.
    Each product will have its own set of action buttons.
    """
    keyboard = []

    for pid, p in favorites.items():
        name = p.get("name", "Product")

        # Row 1: Product Name (Visual separator/label)
        keyboard.append([InlineKeyboardButton(f"📍 {name}", callback_data="none")])

        # Row 2: Actions for this specific product
        keyboard.append(
            [
                InlineKeyboardButton(
                    "📊 History", callback_data=f"price_history_{pid}"
                ),
                InlineKeyboardButton("🛒 Add", callback_data=f"fav_to_cart_{pid}"),
                InlineKeyboardButton("🗑 Remove", callback_data=f"delete_{pid}"),
            ]
        )

    # Bottom menu
    keyboard.append(
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
    )

    return InlineKeyboardMarkup(keyboard)
