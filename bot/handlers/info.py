from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from utils.message_cache import add_message


async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the bot guide and features with message caching."""
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    info_text = (
        "📖 *Smart Price Assistant - Guide*\n\n"
        "🔍 *Search:* Find products in all stores. Prices are shown in **€** for easy comparison.\n"
        "└ ⚙️ *Tip: You can change your active stores anytime in the Settings menu.*\n\n"
        "🔔 *Smart Basket (Premium):* Automated daily monitoring of your specific grocery list. "
        "Set your time (**09:00** or **18:00**) and get price-drop alerts! 🚀\n\n"
        "⭐ *Favorites:* Save items to track them. The bot monitors these and highlights big discounts with labels.\n\n"
        "🛒 *Smart Cart:* Adding items to your cart unlocks unit-price comparisons (per kg/l) to ensure you're getting the best value.\n\n"
        "👤 *Profile & Settings:* View your current status and preferences.\n"
        "└ 📊 *Track your stats:* See your daily searches, favorites, and cart items.\n"
        "└ 🛡️ *Manage:* Check your subscription level and toggle price alerts.\n\n"
        "🧹 *Clear Chat:* Keep your workspace tidy! Use the '**Clear Chat**' button in the main menu to remove old bot messages.\n\n"
        "💡 *Tip:* Upgrade to **Premium** to unlock unlimited favorites, smart price history, and automated basket alerts!"
    )

    keyboard = [
        [InlineKeyboardButton("🚀 Upgrade to Premium", callback_data="subscription")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await query.message.edit_text(
        text=info_text,
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN,
    )

    add_message(user_id, msg.message_id)
