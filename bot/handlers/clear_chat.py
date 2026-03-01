from telegram import Update, constants
from telegram.ext import ContextTypes

from utils.menu import main_menu_keyboard
from utils.message_cache import add_message, clear_messages, get_messages


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if query:
        await query.answer("Cleaning up...")

    # Get all stored message IDs
    message_ids = get_messages(user_id)

    if message_ids:
        # Telegram allows deleting up to 100 messages at once
        # Split into chunks of 100 if necessary
        for i in range(0, len(message_ids), 100):
            chunk = message_ids[i : i + 100]
            try:
                await context.bot.delete_messages(chat_id=chat_id, message_ids=chunk)
            except Exception:
                # Fallback for old messages or already deleted ones
                pass

    # Wipe from local DB
    clear_messages(user_id)

    # Send confirmation and main menu
    text = "✨ *Chat cleared successfully!*"
    reply_markup = main_menu_keyboard(user_id)

    try:
        # Try to reuse the current message if it was a callback
        if query:
            msg = await query.message.edit_text(
                text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN
            )
        else:
            msg = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
    except:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=constants.ParseMode.MARKDOWN,
        )

    # Save the new menu message ID so it can be cleared next time
    add_message(user_id, msg.message_id)
