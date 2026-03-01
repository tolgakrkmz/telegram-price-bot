from db.repositories.user_repo import create_user_if_not_exists
from utils.menu import main_menu_keyboard
from utils.message_cache import add_message


async def start(update, context):
    user = update.effective_user
    create_user_if_not_exists(user)
    user_id = user.id

    # Save user's /start command to be cleared
    if update.message:
        add_message(user_id, update.message.message_id)

    # Pass user_id to the keyboard function
    msg = await update.message.reply_text(
        "🏠 *Main Menu*",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="Markdown",
    )

    # Save the menu message ID
    add_message(user_id, msg.message_id)
