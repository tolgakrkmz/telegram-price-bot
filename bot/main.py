import logging
import datetime
import pytz
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    ConversationHandler, 
    MessageHandler, 
    filters
)
from config.settings import TELEGRAM_TOKEN
from handlers.start import start
from handlers.search import search_start, search_input, SEARCH_INPUT
from handlers.clear_chat import clear_chat
from handlers.favorites import (
    list_favorites, 
    add_to_favorite_callback, 
    delete_favorite_callback,
    view_price_history_callback
)
from handlers.shopping import (
    add_to_shopping_callback,
    clear_shopping_callback,
    confirm_clear_callback,
    list_shopping,
    remove_shopping_callback,
)
from handlers.alerts import update_favorites_prices, global_price_update
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message
from handlers.info import show_info

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def button_handler(update, context):
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
        await query.message.edit_text("🏠 Main Menu:", reply_markup=main_menu_keyboard())

def main():
    """Starts the Telegram bot with Scheduler."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # --- Job Queue (Automation) ---
    job_queue = app.job_queue
    timezone = pytz.timezone('Europe/Sofia')
    
    # Schedule global update every day at 09:00 AM
    job_queue.run_daily(
        global_price_update, 
        time=datetime.time(hour=9, minute=0, second=0, tzinfo=timezone)
    )

    # --- Core Commands ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("update_prices", update_favorites_prices))

    # --- Search Logic ---
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search$")],
        states={SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_input)]},
        fallbacks=[CallbackQueryHandler(button_handler, pattern="^main_menu$")],
        allow_reentry=True
    )
    app.add_handler(search_conv)

    # --- Favorites & Shopping ---
    app.add_handler(CallbackQueryHandler(list_favorites, pattern="^list_favorites$"))
    app.add_handler(CallbackQueryHandler(add_to_favorite_callback, pattern="^add_favorite_.*"))
    app.add_handler(CallbackQueryHandler(delete_favorite_callback, pattern="^delete_.*"))
    app.add_handler(CallbackQueryHandler(list_shopping, pattern="^shopping_list$"))
    app.add_handler(CallbackQueryHandler(add_to_shopping_callback, pattern="^add_shopping_.*"))
    app.add_handler(CallbackQueryHandler(remove_shopping_callback, pattern="^remove_shopping_.*"))
    app.add_handler(CallbackQueryHandler(confirm_clear_callback, pattern="^confirm_clear$"))
    app.add_handler(CallbackQueryHandler(clear_shopping_callback, pattern="^clear_shopping$"))
    app.add_handler(CallbackQueryHandler(list_shopping, pattern="^view_shopping$"))
    app.add_handler(CallbackQueryHandler(view_price_history_callback, pattern="^price_history_"))

    app.add_handler(CallbackQueryHandler(show_info, pattern="^bot_info$"))


    # --- Generic Buttons ---
    app.add_handler(CallbackQueryHandler(button_handler))

    print("🚀 Master-Class Multi-User Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()