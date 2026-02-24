from db.repositories.user_repo import create_user_if_not_exists
from utils.menu import main_menu_keyboard


async def start(update, context):
    create_user_if_not_exists(update.effective_user)
    user_id = update.effective_user.id
    # Pass user_id to the keyboard function
    await update.message.reply_text(
        "🏠 Main Menu", reply_markup=main_menu_keyboard(user_id)
    )
