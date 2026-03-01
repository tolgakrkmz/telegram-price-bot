from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from db.repositories.favorites_repo import get_user_favorites
from db.repositories.shopping_repo import get_user_shopping_list
from db.repositories.user_repo import (
    get_user_subscription_status,
    FREE_USER_DAILY_LIMIT,
)


async def view_profile_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Displays the user profile with current stats and subscription status."""
    query = update.callback_query
    user = update.effective_user
    user_id = user.id

    # Fetch the full status to trigger reset logic and get fresh daily counts
    user_status = get_user_subscription_status(user_id)

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

    if is_premium:
        badge = "💎 **PREMIUM USER**"
        status_text = (
            f"{badge}\n\n"
            f"✅ **Unlimited** Searches\n"
            f"✅ **Unlimited** Favorites\n"
            f"✅ **Unlimited** Shopping Cart\n"
            f"✅ **Price Drop Alerts** Active\n"
            f"✅ **Smart Comparison** Enabled\n\n"
            f"📊 **Your Stats Today:**\n"
            f"⭐ Favorites: {len(favs)}\n"
            f"🛒 Cart items: {len(cart)}\n"
            f"👀 Searches: {daily_requests} (Unlimited)"
        )
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]
    else:
        badge = "👤 **FREE USER**"
        status_text = (
            f"{badge}\n\n"
            f"⚠️ **Daily Limits:**\n"
            f"👀 Searches: {daily_requests}/{FREE_USER_DAILY_LIMIT}\n"
            f"⭐ Favorites: {len(favs)}/3\n"
            f"🛒 Cart items: {len(cart)}/5\n\n"
            f"✨ **Upgrade to Premium for 2.50€ to get:**\n"
            f"🚀 **Unlimited Searches**\n"
            f"🔔 **Price Alerts**\n"
            f"📊 **Full Price History**\n"
            f"📈 **No limits on Favorites ⭐ / Cart 🛒**"
        )
        buttons = [
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
