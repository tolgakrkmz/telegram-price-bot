from telegram import Update
from telegram.ext import ContextTypes

from db.repositories.user_repo import toggle_notifications
from utils.menu import main_menu_keyboard


async def toggle_notifications_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    user_id = query.from_user.id

    # 1. Change state in Supabase
    new_state = toggle_notifications(user_id)

    # 2. Answer callback to remove loading animation
    state_str = "ON" if new_state else "OFF"
    await query.answer(f"Notifications turned {state_str}")

    # 3. Edit the message with the updated keyboard (refreshing the text)
    await query.edit_message_reply_markup(reply_markup=main_menu_keyboard(user_id))
