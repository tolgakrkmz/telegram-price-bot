from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from handlers.search import search_start, search_input, get_search_keyboard
from config.settings import TELEGRAM_TOKEN

SEARCH_INPUT = 1

async def start(update, context):
    await update.message.reply_text(
        "Добре дошли! Използвай бутона по-долу за търсене на продукти:",
        reply_markup=get_search_keyboard()
    )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^search_product$")],
        states={SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_input)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(search_conv)

    print("Ботът стартира...")
    app.run_polling()

if __name__ == "__main__":
    main()
