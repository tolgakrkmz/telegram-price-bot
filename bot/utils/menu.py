from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔍 Търси продукт", callback_data="search")],
        [InlineKeyboardButton("🧹 Изчисти чат", callback_data="clear_chat")],
        [InlineKeyboardButton("📂 Категории", callback_data="categories")]
    ]
    return InlineKeyboardMarkup(keyboard)
