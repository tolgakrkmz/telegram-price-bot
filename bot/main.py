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
from handlers.search import search_start, search_input
from handlers.clear_chat import clear_chat
from utils.menu import main_menu_keyboard

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "clear_chat":
        await clear_chat(update, context)
    elif query.data == "categories":
        msg = await query.message.reply_text("Списък с категории (скоро ще е готово)")
        from utils.message_cache import add_message
        add_message(update.effective_user.id, msg.message_id)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # /start команда
    app.add_handler(CommandHandler("start", start))

    # ConversationHandler за търсене
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="search")],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_input)]
        },
        fallbacks=[]
    )
    app.add_handler(search_conv)

    # Callback бутони за другите действия
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Ботът работи...")
    app.run_polling()

if __name__ == "__main__":
    main()
