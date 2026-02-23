from telegram import Update
from telegram.ext import ContextTypes

from utils.menu import main_menu_keyboard
from utils.message_cache import add_message, clear_messages, get_messages


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    for msg_id in get_messages(user_id):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass

    clear_messages(user_id)

    msg = await context.bot.send_message(
        chat_id=chat_id, text="Чатът е изчистен! 🧹",
        reply_markup=main_menu_keyboard(user_id)
    )    
    add_message(user_id, msg.message_id)
