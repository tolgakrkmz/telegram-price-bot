import datetime
import logging

import pytz
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config.settings import TELEGRAM_TOKEN
from db.repositories.user_repo import get_user_subscription_status, is_user_premium
from handlers.alerts import (
    check_expiring_alerts,
    check_expiring_tomorrow_alerts,
    global_price_update,
    handle_toggle_alerts,
    update_favorites_prices,
)
from handlers.clear_chat import clear_chat
from handlers.favorites import (
    add_to_favorite_callback,
    delete_favorite_callback,
    list_favorites,
    view_price_history_callback,
)
from handlers.info import show_info
from handlers.profile import view_profile_callback
from handlers.search import SEARCH_INPUT, search_input, search_start
from handlers.shopping import (
    add_to_shopping_callback,
    clear_shopping_callback,
    confirm_clear_callback,
    list_shopping,
    remove_shopping_callback,
)
from handlers.smart_basket import (
    SB_CHANGE_SEARCH,
    SB_INPUT,
    SB_REVIEW,
    SB_SELECT_REPLACEMENT,
    SB_TIME,
    confirm_clear_basket,
    execute_clear_basket,
    finalize_replacement,
    handle_change_request,
    handle_new_basket_confirm,
    handle_sb_input,
    handle_time_edit,
    handle_time_selection,
    process_replacement_search,
    show_basket_review,
    smart_basket_job,
    smart_basket_start,
    start_new_basket_flow,
)
from handlers.start import start
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
FREE_DAILY_LIMIT = 5


async def check_limits_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Checks if the user has reached their daily limit before allowing specific actions.
    This logic can be expanded or called within specific entry points.
    """
    user_id = update.effective_user.id

    if await is_user_premium(user_id):
        return True

    status = get_user_subscription_status(user_id)
    if status and status["daily_request_count"] >= FREE_DAILY_LIMIT:
        text = (
            f"⚠️ You have reached your daily limit of {FREE_DAILY_LIMIT} requests.\n\n"
            "Upgrade to ⭐ Premium for unlimited searches and Smart Shopping Mode!"
        )
        if update.callback_query:
            await update.callback_query.answer(text, show_alert=True)
        else:
            await update.message.reply_text(text)
        return False

    return True


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles generic navigation buttons."""
    query = update.callback_query
    user_id = update.effective_user.id
    await query.answer()

    if query.data == "clear_chat":
        await clear_chat(update, context)
    elif query.data == "categories":
        msg = await query.message.reply_text("📂 Categories: Coming Soon...")
        add_message(user_id, msg.message_id)
    elif query.data == "main_menu":
        await query.message.edit_text(
            "🏠 Main Menu:", reply_markup=main_menu_keyboard(user_id)
        )


def main():
    """Starts the Telegram bot with Scheduler."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Job Queue (Automation) ---
    job_queue = app.job_queue
    timezone = pytz.timezone("Europe/Sofia")

    job_queue.run_daily(
        global_price_update,
        time=datetime.time(hour=9, minute=0, second=0, tzinfo=timezone),
    )

    job_queue.run_daily(
        check_expiring_alerts,
        time=datetime.time(hour=9, minute=30, second=0, tzinfo=timezone),
    )

    job_queue.run_daily(
        check_expiring_tomorrow_alerts,
        time=datetime.time(hour=18, minute=0, second=0, tzinfo=timezone),
    )

    job_queue.run_daily(
        smart_basket_job, time=datetime.time(hour=9, minute=0, tzinfo=timezone)
    )

    job_queue.run_daily(
        smart_basket_job, time=datetime.time(hour=18, minute=0, tzinfo=timezone)
    )

    # --- Core Commands ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("update_prices", update_favorites_prices))

    # --- Notification Toggle ---
    app.add_handler(
        CallbackQueryHandler(handle_toggle_alerts, pattern="^toggle_alerts$")
    )

    # --- Search Logic (With Limit Check) ---
    # Note: The actual limit increment should happen inside search_input
    # after a successful API call to avoid wasting limits on typos.
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search$")],
        states={
            SEARCH_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, search_input)
            ]
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern="^main_menu$")],
        allow_reentry=True,
    )
    app.add_handler(search_conv)

    # --- SMART BASKET ---

    smart_basket_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(smart_basket_start, pattern="^smart_basket$"),
            CallbackQueryHandler(start_new_basket_flow, pattern="^sb_new_start$"),
            CallbackQueryHandler(show_basket_review, pattern="^sb_edit_existing$"),
        ],
        states={
            SB_TIME: [CallbackQueryHandler(handle_time_selection, pattern="^sbtime_")],
            SB_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sb_input)
            ],
            SB_REVIEW: [
                CallbackQueryHandler(handle_change_request, pattern="^sb_change_"),
                CallbackQueryHandler(handle_time_edit, pattern="^sb_edit_time_only$"),
                CallbackQueryHandler(
                    confirm_clear_basket, pattern="^sb_clear_confirm$"
                ),
                CallbackQueryHandler(
                    handle_new_basket_confirm, pattern="^sb_new_confirm$"
                ),
                CallbackQueryHandler(execute_clear_basket, pattern="^sb_clear_final$"),
            ],
            SB_CHANGE_SEARCH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, process_replacement_search
                )
            ],
            SB_SELECT_REPLACEMENT: [
                CallbackQueryHandler(finalize_replacement, pattern="^sb_rep_"),
                CallbackQueryHandler(show_basket_review, pattern="^sb_back$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(button_handler, pattern="^main_menu$")],
        allow_reentry=True,
    )
    app.add_handler(smart_basket_conv)

    # --- Favorites & Shopping ---
    app.add_handler(CallbackQueryHandler(list_favorites, pattern="^list_favorites$"))
    app.add_handler(
        CallbackQueryHandler(add_to_favorite_callback, pattern="^add_favorite_.*")
    )
    app.add_handler(
        CallbackQueryHandler(delete_favorite_callback, pattern="^delete_.*")
    )
    app.add_handler(CallbackQueryHandler(list_shopping, pattern="^shopping_list$"))
    app.add_handler(
        CallbackQueryHandler(add_to_shopping_callback, pattern="^add_shopping_.*")
    )
    app.add_handler(
        CallbackQueryHandler(remove_shopping_callback, pattern="^remove_shopping_.*")
    )
    app.add_handler(
        CallbackQueryHandler(confirm_clear_callback, pattern="^confirm_clear$")
    )
    app.add_handler(
        CallbackQueryHandler(clear_shopping_callback, pattern="^clear_shopping$")
    )
    app.add_handler(CallbackQueryHandler(list_shopping, pattern="^view_shopping$"))
    app.add_handler(
        CallbackQueryHandler(view_price_history_callback, pattern="^price_history_")
    )

    app.add_handler(CallbackQueryHandler(show_info, pattern="^bot_info$"))

    app.add_handler(
        CallbackQueryHandler(handle_toggle_alerts, pattern="^toggle_notifications$")
    )

    app.add_handler(
        CallbackQueryHandler(view_profile_callback, pattern="^view_profile$")
    )

    # --- Generic Buttons ---
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Master-Class Multi-User Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
