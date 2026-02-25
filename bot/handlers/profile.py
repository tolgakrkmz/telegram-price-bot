from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from db.repositories.favorites_repo import get_user_favorites
from db.repositories.shopping_repo import get_user_shopping_list
from db.repositories.user_repo import get_daily_request_count, is_user_premium

FREE_SEARCH_LIMIT = 5
PREMIUM_SEARCH_LIMIT = 10


async def view_profile_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    user = update.effective_user
    user_id = user.id

    is_premium = is_user_premium(user_id)
    daily_requests = get_daily_request_count(user_id)

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
            f"✅ **Unlimited** Favorites\n"
            f"✅ **Unlimited** Shopping Cart\n"
            f"✅ **Price Drop Alerts** Active\n"
            f"✅ **Smart Comparison** Enabled\n\n"
            f"📊 **Your Stats:**\n"
            f"⭐ Favorites: {len(favs)}\n"
            f"🛒 Cart items: {len(cart)}\n"
            f"👀 Searches today: {daily_requests}/{PREMIUM_SEARCH_LIMIT}"
        )
        buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]]
    else:
        badge = "👤 **FREE USER**"
        status_text = (
            f"{badge}\n\n"
            f"⚠️ **Limits Active:**\n"
            f"⭐ Favorites: {len(favs)}/3\n"
            f"🛒 Cart items: {len(cart)}/5\n"
            f"👀 Searches today: {daily_requests}/{FREE_SEARCH_LIMIT}\n\n"
            f"✨ **Upgrade to Premium for 2.50€ to get:**\n"
            f"🚀 **Smart Shopping Mode**\n"
            f"🔔 **Price Alerts**\n"
            f"📊 **Full Price History**"
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
