from telegram.ext import Application, CommandHandler
from config.settings import TELEGRAM_TOKEN
from bot.handlers.start import start


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    print("🤖 Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
